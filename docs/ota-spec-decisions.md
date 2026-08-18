# OTA Spec 决策登记

本文件只记录决策过程、责任人和落盘目标，不是接口真相源。最终裁定已经写入对应领域合同；任务提示词长期只引用领域合同条款。用户在记录 9 中批准 OTA-DEC-001 至 OTA-DEC-012 并授权冻结规范，以下决定状态均为 `DECIDED`。用户原话与参数细化完整保存在本文末尾。

## OTA-DEC-001 MCU 线端机型与 Cloudflare deviceModel 映射

- 问题描述：BLE `INFO.model` 只有 8 字节 ASCIIZ，正式发布键为 `e-track-at32f435`；冻结材料没有给出唯一映射值。
- 所属领域：MCU identity / Flutter / Cloudflare latest。
- 候选方案：A. `X-Track` 映射到 `e-track-at32f435`；B. 新定义另一个不超过 7 个 ASCII 字符的线端代码并建立显式表；C. 修改二进制合同扩大字段。
- 推荐方案及理由：推荐 A。`X-Track` 已出现在冻结二进制合同的非规范性示例中，满足 7 字符加 NUL，且无需改动冻结字节布局；仍须由产品/协议责任人确认它是否是正式设备族标识。
- 状态：`DECIDED`。
- 用户裁定：`B`；正式线端值为 `E-Track\0`，映射 `e-track-at32f435`，未知名称拒绝。原话见“用户裁定原文”记录 1。
- 决策责任人：产品负责人 + MCU/Cloudflare 协议审查人。
- 受影响任务：`P3-2`, `P3-3`, `P3-5`, `P4-2`, `P5-1`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-DEVICE-MODEL`、`OTA-XC-INFO-MAPPING`。
- 已有裁定依据：`docs/ota-binary-contracts.md` §5.2.1 的 8B 字段和示例；`.github/workflows/firmware-build.yml` 的 `DEVICE_MODEL=e-track-at32f435`。

## OTA-DEC-002 跨系统镜像身份 SHA-256 域

- 问题描述：`fw_header.image_sha256` 使用双零法；patch 基版、`Tools/etu_pack.py` 和现有 `CurrentImageRawSha8` 使用最终 App 文件原始字节 SHA-256。`INFO.image_sha256`、latest `currentImageSha`、D1 base/target hash 必须选择同一域。
- 所属领域：MCU / `.etu` / Flutter / CI / D1。
- 候选方案：A. 全链使用最终 App `image_len` 字节的原始 SHA-256；B. 全链使用 `fw_header.image_sha256` 双零法；C. API 同时携带两种摘要。
- 推荐方案及理由：推荐 A。差分包现有 base SHA、CI 文件比对和已实现 MCU `base_image_sha8` 都以原始最终镜像为基准；选择 A 不改变冻结 `fw_header` 校验算法。C 会长期制造可混用的双身份，风险最高。
- 状态：`DECIDED`。
- 用户裁定：`A`；最终 `app.bin` 全部 `image_len` 字节 raw SHA-256，合法 INFO 是 latest 前置，legacy 身份不明时隔离。原话见记录 1、2。
- 决策责任人：OTA 架构审查人 + MCU/发布链责任人。
- 受影响任务：`P3-2`, `P3-3`, `P3-5`, `P4-1`, `P4-2`, `P5-1`, `P5-2`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-IMAGE-IDENTITY`、`OTA-XC-RELEASE-METADATA`。
- 已有裁定依据：`docs/ota-binary-contracts.md` §1.2、§2.1、§5.2.1；`Tools/etu_pack.py`；`USER/App/Utils/OtaUpdate/OtaUpdate.cpp` 的 raw SHA8 路径。

## OTA-DEC-003 BLE 生产性能门槛与调参准则

- 问题描述：115200 和 500ms 只是实验基线；没有已冻结的最低吞吐、最大丢包/重传、生产波特率、ACK/重传超时、重试次数或总时长门槛。没有先验门槛，P3-4 无法从数据客观选择生产参数。
- 所属领域：BLE/UART 性能与可靠性。
- 候选方案：A. 以功能成功为唯一门槛；B. 先冻结可接受吞吐、错误率和稳定性门槛，再让 P3-4 在 115200..921600 逐档选最高稳定档；C. 固定 921600 后再测。
- 推荐方案及理由：推荐 B。它保留实验价值且避免从观测结果反向拟合门槛；硬件流控仍按冻结规则禁用。
- 状态：`DECIDED`。
- 用户裁定：`B`，并确认推荐数字及统计口径。原话见记录 4、5。
- 决策责任人：产品负责人 + 嵌入式性能责任人。
- 受影响任务：`P3-1`, `P3-3`, `P3-4`, `P3-5`, `P5-1`, `P5-2`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-BLE-TUNING`、`OTA-XC-RETRY-POLICY`。
- 已有裁定依据：`PLAN-OTA.md` §5.1 和 §9；`PLAN-OTA-EXEC.md` P3-4 明确“500ms 为初值非契约”。

## OTA-DEC-004 minAppVersionCode 的查询和阻断语义

- 问题描述：D1/metadata 已有 `min_app_version_code`，P3-3 要求兼容提示，但 firmware latest 当前不接收 App version，也未定义“只提示”还是“禁止下载/传输”。
- 所属领域：Flutter 产品交互 / Worker compatibility。
- 候选方案：A. latest 必填 `appVersionCode`，低于门槛返回 HTTP 426 `CLIENT_TOO_OLD` 并硬阻断；B. 返回更新 metadata，由 Flutter 只提示但允许继续；C. latest 可省略 App 版本，由客户端下载后自行判断。
- 推荐方案及理由：推荐 A。它在下载和 BLE 传输前 fail closed，避免旧 App 误解新 schema/transport；UI 应给出明确升级 App 的操作说明。
- 状态：`DECIDED`。
- 用户裁定：`A`；latest 强制 App gate，范围 `0..2100000000`，非法 400，过旧 426。原话见记录 1、2、3。
- 决策责任人：产品负责人 + Flutter/Worker 责任人。
- 受影响任务：`P3-3`, `P3-5`, `P4-2`, `P5-1`, `P5-2`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-COMPATIBILITY`、`OTA-XC-HTTP-LATEST`、`OTA-XC-HTTP-ERROR`。
- 已有裁定依据：`PLAN-OTA.md` §6.3；`PLAN-OTA-EXEC.md` P3-3；现有 `firmware_releases.min_app_version_code` 和 `CLIENT_TOO_OLD` error code。

## OTA-DEC-005 HTTP 下载恢复与 Range 策略

- 问题描述：Flutter 当前删除 `.part` 后从零下载，Worker/R2 当前未实现 Range 合同；产品未决定取消、断网和进程重启后的恢复体验。
- 所属领域：Flutter download / Worker / R2。
- 候选方案：A. v1 明确不支持 Range，取消/失败删除 `.part` 并整包重下；B. 支持单区间 `bytes=N-`，绑定 ETag/asset sha 并返回 206；C. 支持多区间和分块合并。
- 推荐方案及理由：推荐 B。固件包可能数百 KB，单区间恢复实现复杂度可控；必须以 assetId/sha/size 绑定，metadata 变化时从零开始。C 超出 v1 必要复杂度。
- 状态：`DECIDED`。
- 用户裁定：`B`，并确认单区间、24 小时 partial、sidecar/ETag/摘要规则。原话见记录 4。
- 决策责任人：Flutter/Worker 技术负责人 + 产品负责人。
- 受影响任务：`P3-3`, `P3-5`, `P4-2`, `P5-2`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-HTTP-RESUME`、`OTA-XC-HTTP-DOWNLOAD`。
- 已有裁定依据：当前 `ota_service.dart` 下载实现、当前 R2 streaming 实现；冻结计划没有 Range 规则。

## OTA-DEC-006 正式 full/patch 资产命名

- 问题描述：recovery 名称已冻结，但正式 full/patch 只有角色名，没有唯一文件名；GitHub Release、R2、D1、Flutter 和审计证据都需要稳定名称。
- 所属领域：CI release / R2 / D1 / Flutter。
- 候选方案：A. `e-track-at32f435-v{target}-full.etu` 与 `e-track-at32f435-v{base}-to-v{target}-patch.etu`；B. `full-v{target}.etu` 与 `patch-v{base}-v{target}.etu`；C. 固定 `full.etu`/`patch.etu`。
- 推荐方案及理由：推荐 A。名称自描述且跨 release 不碰撞；patch 名明确基版和目标版。C 依赖目录上下文，证据脱离目录后容易误认。
- 状态：`DECIDED`。
- 用户裁定：`A`；采用规范 X.Y.Z、确定性文件名和远端写入前校验。原话见记录 6。
- 决策责任人：发布责任人 + 产品/运营审查人。
- 受影响任务：`P4-1`, `P5-1`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-ASSET-NAMING`、`OTA-XC-RELEASE-METADATA`。
- 已有裁定依据：`PLAN-OTA.md` §5.3/§6.1；`PLAN-OTA-EXEC.md` P4-1；现有脚本要求 plain file name 和 immutable release URL。

## OTA-DEC-007 patch 基版与旧资产保留策略

- 问题描述：计划要求“差分基版包保留策略”，但没有保留版本数、天数、引用保护和删除审批规则。
- 所属领域：D1/R2 成本、运营和可恢复性。
- 候选方案：A. v1 所有正式资产永久保留；B. 引用保护 + 最近 N 个正式版本/至少 T 天；C. channel 撤回后即可清理。
- 推荐方案及理由：推荐 B，但 N/T 必须由责任人给出。任何被 ready/published patch 引用的基版在引用解除前绝不删除；recovery 单独受人工保留策略保护。
- 状态：`DECIDED`。
- 用户裁定：`B`；`N=10`、`T=365`、同时超出、引用保护、30 天隔离和双人批准。原话见记录 6。
- 决策责任人：产品/运营负责人 + Cloudflare 成本责任人。
- 受影响任务：`P4-2`, `P4-3`, `P5-2`, `P5-3`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-D1-RETENTION`、`OTA-XC-R2-IMMUTABILITY`。
- 已有裁定依据：`PLAN-OTA.md` §6.2-3；当前 R2 immutable 缓存设计。

## OTA-DEC-008 P4-1 演练与 OTA_BOOT_CHAIN_READY 解锁顺序

- 问题描述：冻结规则要求 P4-1 演练通过后由 P4-1 置 `OTA_BOOT_CHAIN_READY`，但当前正式 job 在变量不为 true 时首步硬失败，无法先走完整正式发布/注册链，形成顺序闭环。
- 所属领域：GitHub Actions 治理 / 发布审批。
- 候选方案：A. 两阶段：锁内只做三资产和 metadata/R2 staging 演练，独立复核通过后人工置 true，再做一次 production dispatch；B. 临时置 true 完成演练后再决定是否保留；C. 移除 gate。
- 推荐方案及理由：推荐 A。它保留冻结的 fail-closed gate，不用临时绕过生产保护；第二阶段才创建正式 Release 和 ready 记录。需进一步明确 staging 资源和“演练通过”的证据边界。
- 状态：`DECIDED`。
- 用户裁定：`A`；独立 rehearsal/staging、生产零副作用证据、独立 reviewer 和人工可审计 gate。原话见记录 6。
- 决策责任人：仓库 owner + 发布治理审查人。
- 受影响任务：`P4-1`, `P4-4`, `P5-1`, `P5-2`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-RELEASE-GATE`、`OTA-XC-SECRETS`。
- 已有裁定依据：`PLAN-OTA-EXEC.md` P1-2 A9c 和 P4-1；`.github/workflows/firmware-build.yml` 当前 gate 顺序。

## OTA-DEC-009 P4 注册链依赖顺序与独立 schema fixture 边界

- 问题描述：看板 P4-1 的显式依赖只有 PRE-3/PRE-4/P0-2，但其正式完成判据要求调用 P4-2 的多资产 register API 并得到 D1 ready；P4-2 原提示词又要求先消费 P4-1 实际 metadata，形成实现顺序循环。P3-5 的手机闭环同样必须消费 P4-2 latest/选包/下载链，但看板卡未列该依赖。
- 所属领域：任务治理 / CI release / Worker-D1 集成顺序。
- 候选方案：A. P4-2 先基于共享合同的 versioned schema fixture 独立实现和验证 register/latest/D1，P4-1 随后接入真实三资产产物，P3-5 等待 P4-2；B. P4-1 自建临时 register stub 并把 D1 ready 排除出完成判据；C. 两卡并行修改同一 scripts/schema，最后一次性消解冲突。
- 推荐方案及理由：推荐 A。它保留 P4-1 的端到端完成判据，避免临时 API 成为第二真相源，也避免 P4-1/P4-2 同时改注册脚本造成竞争；P4-2 的 fixture 必须直接由 `OTA-XC-RELEASE-METADATA` 和 `OTA-XC-HTTP-REGISTER` 生成，不依赖 P4-1 未完成产物。
- 状态：`DECIDED`。
- 用户裁定：`A`，`PARAMS=CONFIRM_RECOMMENDED`。依赖方向为 `P4-2 -> P4-1`、`P4-2 -> P3-5`；P4-1/P3-5 无自动依赖，P4-2 不依赖 P4-1。原话见记录 7 和本轮授权记录 8。
- 决策责任人：看板 owner + OTA 架构审查人。
- 受影响任务：`P3-5`, `P4-1`, `P4-2`。
- 最终落盘目标：经 owner 批准后更新 `PLAN-OTA-EXEC.md` 的 P3-5/P4-1/P4-2 显式依赖，并保留对应提示词中的 fixture/集成边界。
- 已有裁定依据：`PLAN-OTA-EXEC.md` P3-5、P4-1、P4-2；`docs/ota-prompts/prompt-P3-5-integration.md`、`prompt-P4-1-implementation.md`、`prompt-P4-2-implementation.md` 的输入和完成判据。

## OTA-DEC-010 旧 firmware release 的 v2 必填身份字段回填来源

- 问题描述：现有 `0003_firmware_releases.sql` 没有 `target_image_sha256`、`hardware_rev`、`layout_id`、`min_boot_version`、`min_protocol_version`，且 `target_hardware` 可为 NULL；v2 release 模型要求这些字段全部非空。旧资产 `sha256` 是下载文件摘要，不必然等于目标镜像身份，现有表也没有足以确定其余字段的权威来源。
- 所属领域：D1 migration / release identity / 历史数据隔离。
- 候选方案：A. 使用与 release id、commit、原始 artifact 和校验结果绑定的版本化 backfill manifest，只有字段齐全且 artifact 可验证的旧记录才进入 v2，其他记录保持 legacy 隔离并阻止切换规范读路径；B. 从旧资产、机型或当前默认配置推导缺失字段；C. 用 0、空串或固定硬件值补齐后全部保持 draft。
- 推荐方案及理由：推荐 A。它保留字段来源和可重放证据，不把资产摘要冒充镜像身份，也不会让哨兵值进入兼容/选包判断。B/C 会把无法证明的推断永久固化为 release 身份。
- 状态：`DECIDED`。
- 用户裁定：`A`，`PARAMS=CONFIRM_RECOMMENDED`；版本化 manifest 验证后选择性进入 v2，其他记录 legacy 隔离。原话见记录 7。
- 决策责任人：Cloudflare/D1 迁移责任人 + OTA 发布链审查人。
- 受影响任务：`P4-2`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-D1-RELEASE`、`OTA-XC-D1-MIGRATION`，以及 P4-2 migration/backfill 实施说明。
- 已有裁定依据：`app/bluetooth_flutter_Trace/cloudflare/update-service/migrations/0003_firmware_releases.sql` 的现有列；`OTA-XC-IMAGE-IDENTITY` 对 asset digest 与 target image identity 的区分；旧数据不可验证时不得标 ready 的既有迁移红线。

## OTA-DEC-011 Admin release action 幂等键与 recovery 重试窗口

- 问题描述：`disable` 和 `recovery-download` 没有 channel revision，却要求区分首次操作、网络未知结果重试和新操作。现有 `X-Request-Id` 可选，`audit_logs.request_id` 非唯一；没有 key 载体、唯一范围、request fingerprint、保存期限、冲突规则，也没有 recovery URL 过期后是否重签及是否新增 audit 的规则。
- 所属领域：Admin HTTP / D1 / Access identity / audit / download capability。
- 候选方案：A. 两个 release action 都强制 `Idempotency-Key`，唯一范围为 Access actor + key，fingerprint 固定覆盖 method、规范化 path 和 canonical JSON body；保存 24 小时，同 key/同 fingerprint 在 recovery URL 有效期内返回首次 status/body/requestId 且不新增 audit/token，同 key/不同 fingerprint 返回 409，recovery URL 过期后同 key 返回稳定过期冲突并要求新 key，新 key 才签发新 token 和新 audit。B. 仍使用 caller-supplied `X-Request-Id` 兼任幂等键并保存 7 天，其他冲突规则同 A。C. disable 仅按状态机处理，recovery 每次都签发新 token 和新 audit，不提供网络未知结果幂等恢复。
- 推荐方案及理由：推荐 A。专用 key 不污染链路 requestId，actor scope 防止跨主体碰撞，fingerprint 可阻止 key 被复用于另一 release/action；过期 URL 必须使用新 key，避免同一 key 既代表旧响应又产生第二个安全能力。24 小时是待责任人确认的候选窗口，不得在裁定前写入实现。
- 状态：`DECIDED`。
- 用户裁定：`A`，`PARAMS=CONFIRM_RECOMMENDED`；独立 `Idempotency-Key`、actor+key、RFC 8785 fingerprint、24 小时窗口和稳定过期冲突。原话见记录 7。
- 决策责任人：Cloudflare/Admin 安全责任人 + 产品运营负责人。
- 受影响任务：`P4-2`, `P4-3`, `P5-2`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-ADMIN-IDEMPOTENCY`、`OTA-XC-HTTP-ADMIN`、`OTA-XC-D1-AUDIT`，以及对应 D1 migration/清理规则。
- 已有裁定依据：当前 Admin 合同使用可选 `X-Request-Id`；共享 `audit_logs.request_id` 明确不唯一；recovery URL 目标 TTL 为 300 秒。冻结材料没有给出 release action 幂等窗口或持久化规则。

## OTA-DEC-012 下载 token v2 格式与 v1 切换策略

- 问题描述：当前下载 token 没有显式版本，query 只有 `assetId`、`releaseId`、`expiresAt`、`keyVersion`、`signature`，canonical message 也不含 asset kind/purpose；新 recovery 能力必须防止 public token 与 admin token 互换。需要同时确定 v2 完整格式和已签 v1 URL 的切换行为。
- 所属领域：Worker download security / Flutter compatibility / Admin recovery。
- 候选方案：A. 新增 v2，允许 query 恰为 `tokenVersion=2`、`assetId`、`releaseId`、`kind`、`purpose`、`expiresAt`、`keyVersion`、`signature`，拒绝缺失、重复或未知参数；canonical LF 顺序固定为 `2`、uppercase method、assetId、releaseId、kind、purpose、十进制 Unix epoch 秒 expiresAt、keyVersion，signature 继续为 HMAC-SHA256 Base64URL 无 padding。部署后所有新 URL 只签 v2；v1 只允许部署前已签的 full/patch URL 按原 expiresAt 到期，永不允许 recovery，最大 300 秒窗口后删除 v1 verifier。B. signer/verifier 原子切到同一 v2 格式并立即拒绝全部 v1。C. v1/v2 双签双验一个完整 key rotation 周期，再停止 v1。
- 推荐方案及理由：推荐 A。它给已经返回给客户端的 public URL 一个有界 300 秒自然到期窗口，同时从第一天起禁止 v1 recovery；显式版本、精确 query 集合和 canonical 顺序可避免 signer/verifier 漂移。是否接受该窗口仍须安全责任人裁定，不能由实现方根据部署方便选择。
- 状态：`DECIDED`。
- 用户裁定：`A`，并确认推荐参数、固定 cutover 和排他 expiry。原话见记录 4、5。
- 决策责任人：Worker 安全责任人 + Flutter/发布兼容责任人。
- 受影响任务：`P3-3`, `P3-5`, `P4-2`, `P4-3`, `P5-1`, `P5-2`。
- 最终落盘目标：`docs/ota-cross-system-contracts.md` 的 `OTA-XC-HTTP-DOWNLOAD`、`OTA-XC-HTTP-ADMIN` 和相关 token 兼容测试向量。
- 已有裁定依据：`worker/src/downloads.ts` 当前 canonical message 为 `METHOD\nassetId\nreleaseId\nexpiresAt\nkeyVersion`；当前 query 和测试使用 Unix epoch 秒与 300 秒 TTL；冻结材料没有 kind/purpose token 版本或 v1 下线规则。

## 用户裁定原文

以下记录按本轮对话中的接收顺序逐字保存。记录 1 至记录 8 保存候选形成和复核阶段的约束；记录 9 是把全部决定转为 `DECIDED`、把规范转为冻结状态并允许首批任务派单的明确授权。

### 记录 1

~~~text
OTA-DEC-001=B；设备短名称固定为 E-Track（7 个 ASCII 字符，线格式为 E-Track\0），对应云端 e-track-at32f435；未知名称拒绝升级。

OTA-DEC-002=A；跨系统身份使用最终 app.bin 的全部 image_len 字节计算原始 SHA-256；旧记录不猜测，身份不明时只允许 full，不允许 patch。

OTA-DEC-004=A；低于 minAppVersionCode 时返回 CLIENT_TOO_OLD，不提供资产或下载地址；缺少或非法 appVersionCode 也拒绝，在下载和 BLE 传输前阻断。
~~~

### 记录 2

~~~text
OTA-DEC-002-SCOPE=A，但补充以下精确定义：

只有设备通过完整有效的 INFO 提供了合法的 raw currentImageSha，而云端没有与之匹配的已验证 patch 基版，或匹配的 patch 不可用时，才自动退回已验证的 full。

如果 INFO.image_sha256 缺失、长度错误、格式非法或无法计算，应在 Flutter 本地 fail closed，不请求 latest，也不得借 full 绕过设备身份读取。

被返回的 full 必须属于具有权威 targetImageSha256 的有效 release，并通过资产长度、资产 SHA-256、硬件、布局、Boot 和协议兼容检查。

历史 release 如果缺少权威目标镜像身份，继续按 OTA-DEC-010 保持 legacy 隔离，不得进入 latest，也不得因为存在 full 文件而自动放行。


OTA-DEC-004-PARAMS=CONFIRM，并补充：

latest 强制要求 appVersionCode。缺失、空值、非十进制整数、负数或超出支持整数范围时，返回 HTTP 400 INVALID_PARAMETER。

存在更新且 appVersionCode 低于 release.minAppVersionCode 时，返回 HTTP 426 CLIENT_TOO_OLD；响应必须包含 minAppVersionCode，且不得包含 asset、下载 URL、签名或其他取包信息。

判定顺序为：参数校验和限流 → 加载有效 channel/release → 确认存在更新 → App 版本门禁 → 设备兼容与选包 → 签发 URL。

download 不接收也不重复校验 appVersionCode。它继续校验签名 token、purpose、release/asset 状态、有效期和资产身份；App 版本兼容性以 latest 签发前门禁为准。

Flutter 收到 CLIENT_TOO_OLD 后必须保持终止状态，不得进入下载或 BLE；不得将其转换为 NO_UPDATE。
~~~

### 记录 3

~~~text
OTA-DEC-004-RANGE=A。

appVersionCode 和 minAppVersionCode 的合法范围统一为 0..2100000000，包含两端，与 Android/Google Play versionCode 上限一致。

缺失、非整数、负数或大于 2100000000 均返回 HTTP 400 INVALID_PARAMETER。发布注册和 D1 写入也必须拒绝超出该范围的 minAppVersionCode，避免产生任何客户端都无法满足的 release。
~~~

### 记录 4

~~~text
OTA-DEC-003=B
OTA-DEC-003-PARAMS=CONFIRM_RECOMMENDED

数字不修改，补充以下统计口径：

referencePackageBytes 指 BLE 实际传输的完整合法 .etu 总字节数，不是解包后的 image_len。

singleRun/p95 计时边界统一为发送 BEGIN 到收到成功 END ACK；包含正常 ACK 等待和重传时间，不包含 latest 和 HTTP 下载。

effectiveThroughputKiBps = package total_len / 上述完整耗时，不能使用“首次发送字节数”或 UART/GATT 物理字节数美化吞吐。

dataRetransmissionRate = 重传 DATA 帧数 / 完成该包所需的唯一 DATA 段数。1% 门槛只用于无主动注错的 clean runs；丢段、乱序和断连注错单独按恢复判据验收。

P99_ACK 取同一候选波特率 clean runs 中，从完整 DATA 帧发送完成到对应有效 ACK 到达的样本；timeout = clamp(3×P99_ACK, 500ms, 2000ms)。

30 次连续成功、4 小时 soak、10/10 重连恢复和其他门槛必须由同一个候选参数组合全部满足，不得从不同档位拼接结果。


OTA-DEC-005=B
OTA-DEC-005-PARAMS=CONFIRM_RECOMMENDED

修改和补充以下项目：

localPartSize 等于 sizeBytes 时，不发送 Range；先验证整文件 SHA-256，验证通过则原子转为完成文件，失败才删除并重新 latest。

localPartSize 大于 sizeBytes 时，立即删除旧 .part 并重新 latest。

服务器实际收到 bytes=N- 且 N>=sizeBytes 时返回 416；Flutter 删除该 .part 并重新 latest。

206 必须返回 Accept-Ranges: bytes、Content-Range、Content-Length 和与 If-Range 一致的强 ETag。If-Range 不匹配而返回 200 时，Flutter 必须先截断旧文件，禁止把 200 body 追加到 .part。

206 的 Content-Digest 如果存在，只表示本次响应 body，不得冒充完整资产摘要。完整资产身份始终以 metadata sha256 为准，并在组装完成后重算整文件 SHA-256。完整 200 响应的 Content-Digest 才表示完整响应文件。

保留的 .part 必须有原子 sidecar metadata，记录 assetId、releaseId、sha256、sizeBytes、ETag 和更新时间；任一身份字段变化立即作废。

超过 partialRetentionHours 的 .part 和 sidecar 必须清理，不能仅限制为每个 asset 一个而无限积累历史 asset。


OTA-DEC-012=A
OTA-DEC-012-PARAMS=CONFIRM_RECOMMENDED

补充以下切换边界：

部署时必须记录固定且可审计的 v2CutoverEpoch，不能使用 Worker 进程启动时间或每次部署时间动态重置兼容窗口。

v1 verifier 只接受精确的旧 query 集合，并且必须同时满足：
- 资产实际类型为 full 或 patch。
- 用途只能按 public-ota 处理。
- expiresAt 不晚于 v2CutoverEpoch+300。
- 当前时间未超过 token 自身 expiresAt。
- recovery 始终拒绝。

从 v2CutoverEpoch 起所有 signer 只生成 v2。到 v2CutoverEpoch+300 时，运行时必须自动拒绝全部 v1；不得依赖人工恰好在该秒完成部署。

v1 verifier 源码在兼容窗口结束后的首个部署中删除，但行为上的拒绝必须从窗口截止时刻立即生效。

部署回滚不得恢复 v1 signer。若必须回滚，应保留 v2 signer/verifier，或暂时停止签发下载 URL，不能重新产生 v1 URL。
~~~

### 记录 5

~~~text
OTA-DEC-003-THROUGHPUT=CONFIRM

effectiveThroughputKiBps = referencePackageBytes / 1024 / elapsedSeconds。

elapsedSeconds 使用单调时钟测量，从 BEGIN 首字节开始发送到成功 END ACK 完整到达；不得使用系统墙钟，计时无效或结果小于等于 0 时该轮实验无效。


OTA-DEC-003-ACK-SAMPLE=A

按推荐定义执行。补充：

同一候选参数组合的全部 clean run 有效样本合并计算，不得跨不同 baud、timeout 或 retry 配置混合。

P99 使用 nearest-rank：将 N 个延迟样本升序排列，取第 ceil(0.99×N) 个样本；不使用插值，也不得删除合法的高延迟样本。

延迟使用单调高精度时钟测量。某个 clean run 最终失败或存在无法确认的 DATA 段时，该轮不能通过成功门槛，也不得通过删除缺失样本美化 P99。


OTA-DEC-012-EXPIRY=A

expiresAt 为排他截止时刻。仅当 currentEpochSeconds < expiresAt 时 token 有效；currentEpochSeconds >= expiresAt 时返回 TOKEN_EXPIRED。

v1 同时要求 currentEpochSeconds < v2CutoverEpoch+300；到达或超过该时刻立即拒绝全部 v1。
~~~

### 记录 6

~~~text
OTA-DEC-006=A

参数采用推荐值，但将正式版本格式收紧为真正的规范化 X.Y.Z：

formalVersionPattern=^(0|[1-9][0-9]*)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)$
allowPrereleaseSuffix=false
fileNameCase=lowercase deviceModel/role，版本数字原样
maxFileNameBytes=128
invalidOrDuplicateName=INVALID_PARAMETER，发布链在任何 GitHub Release、R2、D1 等远端写入前失败

补充规则：
- minor 和 patch 必须为 0..99。
- 禁止 01.02.003 等前导零形式。
- 按冻结公式生成的 versionCode 必须落入 u32。
- patch 的 baseVersionCode 必须小于 targetVersionCode。
- 文件名长度按完整 ASCII 文件名计算，包含扩展名。
- 正式文件名固定为：
  e-track-at32f435-v{targetVersion}-full.etu
  e-track-at32f435-v{baseVersion}-to-v{targetVersion}-patch.etu
- recovery 继续使用 recovery-vX.Y.Z.bin。
- 同一 canonical metadata 重放必须得到同一文件名；同一 release 内不同资产不得同名。


OTA-DEC-007=B

采用推荐参数：

retentionScope=appId+deviceModel
recentFormalReleaseCount=10
minimumRetentionDays=365
eligibilityRule=同时超出 N 和 T
recoveryAutoDelete=false
approval=产品/运营 owner + Cloudflare 成本责任人
archiveQuarantineDays=30
r2Deletion=隔离后再次检查并双人批准
githubReleaseDeletion=默认禁止；另行双人批准
cleanupFrequency=每月一次
referenceProtection=任何 ready patch、stable/beta pointer、未完成注册/恢复/清理任务
auditRequired=true

补充精确定义：
- “最近 10 个”按 version_code 降序计算；version_code 已在同一 appId+deviceModel 内唯一，不使用可变 updated_at 排序。
- 365 天从 firmware_releases.created_at 计算；created_at 创建后不可改写。
- 只有 release 排名在前 10 之外且 ageDays>=365，才可进入候选清理。
- archived 隔离期从成功 archived 状态迁移及其 audit 时间开始计算。
- 隔离期开始前的批准不能代替物理删除前批准；隔离期结束、引用重查通过后，双人必须对最终不可变删除 manifest 再次批准。
- 删除 R2 后保留 D1 release/asset 记录，将资产状态记为 r2_deleted；D1 身份、摘要、状态历史和 append-only audit 不得物理删除。
- recovery 永不进入自动候选。删除 recovery 必须由用户另行授权并走相同双人审批。
- GitHub Release 资产默认永久保留；R2 删除不能自动连带删除 GitHub 资产。
- 任一引用查询、状态查询、审批或审计写入失败时，本轮清理 fail closed，不删除任何对象。


OTA-DEC-008=A

采用推荐参数：

rehearsalEnvironment=firmware-rehearsal
stagingR2Bucket=trace-update-staging-releases
stagingWorker=独立 staging origin
stagingD1=独立 staging database
productionSideEffectsAllowed=false
githubPrereleaseAllowed=false
requiredEvidence=三资产 SHA/size、patch 逐字节自验、recovery 校验、metadata SHA、staging R2 全字节 readback、staging register ready/idempotency、生产资源零副作用
reviewer=独立 OTA 架构审查人
gateSetter=repository owner
gateWriteMode=人工且可审计
gateLifetime=通过后保持 true，Boot/OTA 链回归或证据失效时立即恢复 false
productionApproval=firmware-production environment 独立审批

补充精确定义：
- rehearsal 和 production 必须运行同一 workflow、制包工具、schema 和注册客户端代码，只允许通过 environment bindings 切换 Worker、D1、R2 和凭据。
- rehearsal environment 不得获得任何 production Worker、D1、R2 或发布凭据。
- 首次解锁后的 production 发布必须绑定已批准 rehearsal 的相同 commit、version 输入和 canonical metadata。
- production 在产生任何远端副作用前，必须重新构建并确认三资产及 metadata 摘要与已批准 rehearsal 完全一致；不一致则硬失败并重新 rehearsal。
- 独立 reviewer 不得是该次 rehearsal 的实现作者；gateSetter 只能在 reviewer 明确批准后操作变量。
- 生产资源零副作用必须通过 rehearsal 前后 production D1、R2、channel 和 GitHub Release 快照证明，不能只依赖 workflow 日志中“未执行”。
- 后续普通固件业务代码变化不自动关闭 gate。
- 以下受治理输入发生语义变化时必须先把 gate 恢复 false 并重新 rehearsal：Boot/OTA 状态机、二进制合同、Flash/layout/linker、finalize/pack/unpack、BLE OTA transport、发布 workflow、资产 schema、注册/下载安全合同以及 staging/production 绑定边界。
- 发生生产发布事故、关键验收撤销、受控工具链变化或无法证明 rehearsal 证据仍适用时，也必须 fail closed 并重新锁定。
- 禁止通过临时设置 true、修改 job 条件、使用 staging 凭据访问生产资源或把失败的 production job 作为 rehearsal 证据。
~~~

### 记录 7

~~~text
OTA-DEC-009=A
OTA-DEC-009-PARAMS=CONFIRM_RECOMMENDED

OTA-DEC-010=A
OTA-DEC-010-PARAMS=CONFIRM_RECOMMENDED

OTA-DEC-011=A
OTA-DEC-011-PARAMS=CONFIRM_RECOMMENDED
~~~

### 记录 8

~~~text
现授权你执行 P2-6 后续 OTA Spec 候选落盘，但仅限用户列出的写入白名单和文件范围。

依赖方向解释为“前置任务 -> 后置任务”：
P4-2 -> P4-1
P4-2 -> P3-5
P4-1 与 P3-5 之间无自动依赖
P4-2 不依赖 P4-1

允许更新共享跨系统合同、PLAN-OTA-EXEC.md readiness/依赖字段、受影响任务提示词和决策登记中的用户裁定记录。所有决定记录必须保留用户原话和依据，但不得自行把决定标记为 DECIDED；所有新增或修改规范保持 DRAFT_PENDING_REVIEW，所有受影响任务保持 NOT_DISPATCHABLE。

不得修改生产源码、docs/ota-binary-contracts.md、其他冻结文件；不得创建 migration、fixture 实现或探针；不得运行构建或完整实验；不得 commit、push 或 merge。

若发现依赖方向、冻结状态、现有脏修改或权威合同存在冲突，立即停止编辑并报告，不得自行解释或扩大范围。完成后只报告修改文件、条款传播、readiness 变化、测试结果和剩余阻断。
~~~

### 记录 9

~~~text
批准 OTA-DEC-001 至 OTA-DEC-012，授权冻结规范并进入首批实现；生产部署仍须等待 P5 验收。
~~~

记录 9 仅解除决定、规范成熟度和首批任务派单的候选阶段阻断。它不解除 P5 生产验收门槛，不授权生产部署，也不改变各任务的实际依赖关系。

## CONFIRM_RECOMMENDED 参数快照

本节不是用户逐字原话。它只把记录 7 中由用户明确确认的推荐方案展开为审查快照，依据是各决定上方的候选方案、推荐理由和已传播的共享合同。决定状态转换的唯一授权是记录 9，而不是本节的参数展开。

### OTA-DEC-009

- P4-2 拥有 `schemaVersion=2` 的 versioned schema fixture，唯一来源为 `OTA-XC-RELEASE-METADATA` 与 `OTA-XC-HTTP-REGISTER`。
- fixture 至少覆盖 full/patch/recovery 注册、相同 canonical metadata 重放、同 releaseTag 不同 metadata 冲突、非法或未知字段拒绝。
- 依赖方向为 `P4-2 -> P4-1`、`P4-2 -> P3-5`；P4-2 不依赖 P4-1，P4-1 与 P3-5 无自动依赖。
- P4-1 保留真实三资产 register 后 D1 ready 的完成判据，不得创建临时 register stub 或第二 schema；P3-5 使用真实 P4-2 register/latest/download、R2 readback 和 D1 ready，不得手改 D1 或用任意静态 JSON 冒充真实链。

### OTA-DEC-010

- backfill manifest 固定为不可变、版本化的 `manifestSchemaVersion=1`，绑定 release、commit、run、原始 artifact locator、asset SHA/size、最终 app.bin raw image_len SHA、验证工具和审批证据。
- 只有字段齐全、旧记录逐字段匹配且 artifact 可逐字节验证的记录可进入 v2；任一来源缺失或验证失败均保持 legacy 隔离。
- 禁止用旧 asset 摘要、deviceModel、当前默认值、文件名、0、空串或固定硬件值猜测 identity；legacy 不得进入 latest、patch 基版、full fallback、publish 或 recovery。
- backfill 必须可重入；同一记录和 manifest 重放不改变 identity，manifest 内容变化作为冲突拒绝；channel 指向不可验证 legacy 时规范读切换 fail closed。

### OTA-DEC-011

- `disable` 与 `recovery-download` 强制独立 `Idempotency-Key`，格式为小写 canonical UUIDv4；唯一范围为 Access `actorCanonical + key`，跨两个 release action endpoint。
- fingerprint 为已验证 method、重建后的 canonical path 和 canonical JSON body 的 RFC 8785 UTF-8 字节 SHA-256，编码为 64 位小写 hex。
- 首次成功结果保存 86400 秒；release mutation/audit/result 或 recovery audit/result 必须原子提交，并发同 key 不得产生双重 mutation、token 或 audit。
- 同 key/同 fingerprint 重放原结果；不同 fingerprint 返回 409 `IDEMPOTENCY_CONFLICT`。recovery URL 过期但记录仍有效时返回 409 `IDEMPOTENCY_RESULT_EXPIRED`，必须换新 key 才可重签和新增 audit。
- Cloudflare Cron 每小时清理过期结果，运行时仍按排他 `retainedUntil` 判定；append-only audit 永不清理，key、完整 URL、token 和 signature 不进入 audit 或普通日志。
