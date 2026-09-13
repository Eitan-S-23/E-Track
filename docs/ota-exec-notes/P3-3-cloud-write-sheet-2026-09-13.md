# P3-3 云端（D1/R2/channel）完整写入单与 staging 准入条件 —— 2026-09-13

> 依据：用户 2026-09-13 分项批复第 2、3 条。第 2 条要求受控 HTTP 服务方案的
> 准入条件（部署身份、共享合同兼容性、测试数据隔离——域名可访问、400、
> 独立 URL 路径都不足以证明）；第 3 条要求 D1 fixture 与资产上传先补完整
> 写入单（账号、部署版本、D1 ID、R2 bucket/对象键、appId/deviceModel/channel、
> 记录、写入前快照、资产 SHA/size、命令、次数、超时、清理范围；candidate→
> firmware channel 指针的合法录入方式及 30201→toy 成功→30202 激活步骤；
> 下载路径保留 token/兼容/摘要检查）。
>
> **性质**：纯申报文档。零云端写入、零真机操作、零代码改动、零部署。
>
> **⏸ 暂停状态（2026-09-13 第三轮裁定第 2 条，整体生效）**：
> - **B0-B4 云端写入方案暂停**（B0 写入前快照后的全部写操作序列：
>   B1 元数据构建产物、B2 R2 上传、B3 D1 candidate 登记、B4 stable
>   publish）。本单任何云端写入在解除暂停前不执行。
> - **不申请或传递 Access 会话**：步骤 4 所需的 Access owner 会话不由
>   agent 申请、不由用户代持传递给 agent；解除暂停前不发起。
> - **不修改共享 stable 渠道**：`firmware_channels` stable 指针（含
>   publish/disable 一切路径）不触碰。
> - **替代路线已落地**：P3-3 验收链改走受控 v2 测试服务
>   （`P3-3-v2-service-plan-and-selftest-2026-09-13.md`（v2），受管路径
>   `Tools/ota/p3-3-service/` 四件套，SERVICE_VERSION=2，16 项宿主自测 +
>   tls_hostcheck 宿主 HTTPS 全链 PASS，部署申请待批）。本单降级为 P4-2
>   前置未解除期间的**冻结申报**，不再阻塞 P3-3。
> - **当前本机路线不使用 Cloudflare**（2026-09-13 第四轮裁定第 4 条）：
>   不需要刷新或读取其 token，也不需要用户在聊天中提供凭据。若受控服务
>   HTTPS 路线 B（Cloudflare Named Tunnel，服务文档 v2 §5）最终获批，
>   其账号操作按本单 §9 CF 规约执行。

## 1. 结论先行：staging 共享合同不兼容实锤，方案 A/B 均不可行

用户第 2 条的预判得到源码证实——**域名可访问、400 参数校验、独立 URL 路径
都不足以证明共享合同兼容**。决定性证据：

| 侧 | 事实 | 来源 |
| --- | --- | --- |
| staging worker 固件 latest 端点 | 响应 `schemaVersion: 1`（无 requestId、无 asset 对象、无 targetImageSha256） | `cloudflare/update-service/worker/src/firmware.ts:101` |
| App 端解析器（冻结合同 v2 的实现） | `FirmwareLatestInfo.parse` 要求 `schemaVersion == 2`，否则抛 `OtaLatestParseException('未知 schema major: 1')` **fail-closed 终止** | `app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart` |
| 冻结共享合同 | OTA-XC-HTTP-LATEST v2（FROZEN，波及 P3-3/P4-2/P3-5/P5-1）：v2 JSON、requestId、asset 对象、targetImageSha256、兼容门禁链（409 required/actual）、426 CLIENT_TOO_OLD App 门禁、OTA-XC-ASSET-SELECTION、OTA-XC-HTTP-DOWNLOAD token v2 | `docs/ota-cross-system-contracts.md` |
| 固件 v2 worker 实现 | **不存在**。latest.ts 里的 v2 是 APK 侧；固件 latest/register/download 的 v2 worker 实现属 P4-2（看板 §8.1 状态 DISPATCHABLE，未认领） | 全仓库检索 + `PLAN-OTA-EXEC.md` |

**推论**：

1. 把受验 APK 的固件 endpoint 指向现网 staging（方案 A），App 的第一个
   latest 请求就会因 `schemaVersion=1` 解析失败终止——**fixture 登不登记都
   走不通**，400/可达性观测全部绕不过这一层。
2. 方案 B（从同一份仓库源码部署全新实例）**同样不可行**：部署的是同一份
   v1 源码，schema 不兼容问题原样复制，只是换了个域名。
3. 因此本写入单的**执行前置 = P4-2 先实现并部署 worker 固件端 v2**
   （latest v2 响应 + register v2 元数据（OTA-XC-RELEASE-METADATA assets 数组）
   + download token v2 + D1 多资产记录），或用户裁定的等价物（如用户批准
   为 P3-3 单独放宽 App 端解析——合同冻结约束下不默认可行，须用户明示）。
   **P4-2 属于看板独立任务卡，本单不越卡实现。**
4. 下文写入单**如实保留全部字段**（用户第 3 条要求一次列明），但每处标
   P4-2 前置；批准本单 ≠ 解除该前置。

## 2. staging 资源身份与准入核对（执行前逐项核对，本节是核对方法不是核对结果）

| 项 | 值 / 核对方法 | 来源 |
| --- | --- | --- |
| Cloudflare 账号 | **执行前核对**：`wrangler whoami`（本地 Wrangler 浏览器授权后）记录账号名与 account ID；本会话未持有 Cloudflare 凭证，不猜测 | STAGING-SETUP 流程 |
| 公开 Pages 部署版本 | **执行前核对**：`wrangler pages deployment list --project-name trace-update-public-staging`，记录当前生效 deployment 的 Source commit 与时间。行为证据（`/api/public/firmware/latest` 缺 `deviceModel` 返 400，T1a 观测轮）只证明部署包含 v1 族 firmware.ts，**不证明具体 commit**——部署版本核对本身是准入条件，核对结果回填本表后方可执行写入 | AGENTS.md 既有核对方法 |
| Worker 部署版本 | 同上：`wrangler deployments list`（worker 项目），核对 CI register 所用的 Worker URL 背后版本 | `cloudflare/update-service/worker/wrangler.jsonc` |
| D1 数据库 | database_id `0133ad9e-d4a2-4fef-a659-4f2bf3d3a645`，名 `trace-update-staging` | worker `wrangler.jsonc` staging env |
| R2 bucket | `trace-update-staging-releases` | 同上 |
| 公开端点 | `https://trace-update-public-staging.pages.dev`（仅暴露 `/api/public/*`） | 同上 |
| CI/登记端点 | `TRACE_UPDATE_SERVICE_URL`（Worker URL，`/api/ci/*` 用 Bearer `TRACE_DEPLOY_TOKEN`） | register 脚本 |
| 固定配置 | `APP_ID=trace`、`GITHUB_OWNER=Eitan-S-23`、`GITHUB_REPO=Trace`、`DOWNLOAD_TOKEN_TTL=300`s、token `key_version=staging` | wrangler.jsonc vars |
| 测试数据隔离 | 见 §4 | — |

## 3. 共享合同兼容性逐项核对表（v2 冻结要求 vs staging v1 实况）

| v2 冻结要求（App/合同侧） | staging v1 实况（worker firmware.ts） | 兼容 |
| --- | --- | --- |
| 响应 `schemaVersion: 2` | `schemaVersion: 1`（:101） | **否（决定性）** |
| `requestId` 顶层字段 | 无 | 否 |
| `asset` 对象（assetId/kind/fileName/sha256/sizeBytes/baseVersionCode/baseImageSha256/downloadUrl/expiresAt） | 无 asset 对象（v1 是扁平字段：fileName/sha256/sizeBytes/downloadUrl 等直接平铺） | 否 |
| `targetImageSha256`（终点比对标准=最终镜像 raw SHA） | 无 | 否 |
| 硬件→layout→Boot→协议 兼容门禁链（409 带 required/actual） | 无兼容门禁链实现 | 否 |
| App 版本门禁 `426 CLIENT_TOO_OLD` | 无（v1 只有 `isFirmwareNewer` 比较逻辑） | 否 |
| OTA-XC-ASSET-SELECTION（patch 按 base_image_sha256 匹配、full 兜底） | 无多资产选择（单文件字段） | 否 |
| 下载 token v2（tokenVersion=2/assetId/releaseId/kind/purpose/expiresAt/keyVersion/signature 规范消息） | token v1（assetId/releaseId/expiresAt/keyVersion/signature，`verifyDownloadToken`） | 否 |
| 登记元数据 v2（OTA-XC-RELEASE-METADATA：`assets` 数组，full+patch 分列） | register 请求是 v1 单文件格式（build-firmware-release-metadata.mjs 产物：fileName/sha256/sizeBytes/githubUrl 平铺，无 assets 数组） | 否 |
| App 端身份闭集合（appId=trace、deviceModel=e-track-at32f435、channel 回显校验、kind/后缀/size≤0x180000、full baseVersionCode=0 且 baseImageSha256 键存在值为 null） | v1 响应无法通过 App 解析器（第一行 schema major 即终止），后续字段无从到达 | 否 |

**补充（download 路径语义，用户第 3 条「不能笼统写 R2 或 Pages 静态位」）**：
现网 v1 下载路径本身是真实 token 端点 `GET /api/public/firmware/download`
（`assetId/releaseId/expiresAt/keyVersion/signature` 五参数验签
`verifyDownloadToken` → `loadFirmwareDownloadState` → `ensureFirmwareDownloadAllowed`
（app/channel disable 检查 + 未发布到 channel 时 `ASSET_DISABLED` 410）→ R2
流式 + size 核对，firmware.ts:130-143）。**本单不使用任何静态 R2/Pages 直链**；
P4-2 后按同语义的 token v2 端点执行，App 端整包 SHA-256 校验（C-TOY/C-REAL-LOOP
共同终点的一部分）不旁路。

## 4. 测试数据隔离评估

- 固件数据与 APK 更新数据在 D1 内是**独立表**：`firmware_releases` /
  `firmware_channels`（migration `0003_firmware_releases.sql`）与 APK 侧
  `releases`/`channels` 分离；`/api/public/latest`（APK，现返回 versionCode 86）
  与 `/api/public/firmware/latest`（固件）互不读取对方表。
- 固件记录天然按 `(app_id, device_model)` 隔离：fixture 用
  `app_id='trace'`、`device_model='e-track-at32f435'`，不影响其他
  deviceModel 的任何固件行。
- **未知项（执行前快照回答）**：staging D1 的 `firmware_releases`/
  `firmware_channels` 当前是否有历史行（例如早期验证登记过 2.8.x）。
  快照命令见 §5 步骤 0；若有行，本单 fixture 不得复用其 version_code/
  release_tag（30201/30202 占用检查在仓库侧已通过，云端侧以快照为准）。
- `firmware_channels` 行在首次固件登记时由 worker 自动 `INSERT OR IGNORE`
  创建（firmware.ts:199-203，stable/beta 各一行，`current_release_id` 为
  NULL 直到 publish）——不触碰 APK 侧 channels 表。

## 5. 完整写入单（**P4-2 前置未解除前不执行**；批准的是范围，不是开工令）

### 5.0 写入目标总表

| 字段 | toy 3.2.1 | 真包 3.2.2 |
| --- | --- | --- |
| Cloudflare 账号 | 执行前 `wrangler whoami` 核对回填（§2） | 同左 |
| 部署版本 | 执行前 `wrangler pages deployment list` + `wrangler deployments list` 核对回填（§2，P4-2 后必须是含固件 v2 的部署） | 同左 |
| D1 数据库 | `0133ad9e-d4a2-4fef-a659-4f2bf3d3a645`（trace-update-staging） | 同左 |
| R2 bucket | `trace-update-staging-releases` | 同左 |
| R2 对象键（强制策略 `firmwareR2KeyForRelease`，firmware.ts:591-597） | `trace/firmware/e-track-at32f435/30201-mcu-e-track-at32f435-v3.2.1/e-track-at32f435-v3.2.1-full.etu` | `trace/firmware/e-track-at32f435/30202-mcu-e-track-at32f435-v3.2.2/e-track-at32f435-v3.2.2-full.etu` |
| appId / deviceModel / channel | `trace` / `e-track-at32f435` / **stable**（App 端 `TRACE_UPDATE_CHANNEL` dart-define 默认 `stable`，share_links.dart:9-12；受验 APK 不注入该 define 时查询的就是 stable） | 同左 |
| 涉及记录 | `firmware_releases` 新增 1 行（state=candidate，version_code=30201，release_tag=`mcu-e-track-at32f435-v3.2.1`，UNIQUE(app_id,device_model,version_code)/(release_tag)/(run_id) 三重约束）；`firmware_channels` stable 行 `current_release_id` 改指该记录 | 同左（30202 / `mcu-e-track-at32f435-v3.2.2`） |
| 资产 SHA-256 / size | `fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2` / 284092 B | `0a2eb26a481d8c462b5316a67a151c8241de354d00797fa22f11e77056538ce5` / 284112 B |
| targetImageSha256（登记元数据内，供 App 终点比对） | `43ee943a185f63d70284c7c5a9992d677a9bf8c518dacd2e63df8ec7e5809b55` | `c958221392fade8b40520df2d7fd4278632d64bcdd8261b0ac7536c6468a7f39` |
| 本地实物 | admission worktree `.cache/p3-3-assets/e-track-at32f435-v3.2.1-full.etu`（规范名副本，与原始产物逐字节一致，见离线资产文档 §4.1） | `.cache/p3-3-assets/e-track-at32f435-v3.2.2-full.etu` |

### 5.1 命令序列（每份资产一组；均为仓库既有脚本，无新增云端工具）

**步骤 0 —— 写入前快照（只读，先于一切写操作）**

```
# D1 两表全量快照（结果落盘 docs/ota-exec-notes/ 证据目录）
wrangler d1 execute trace-update-staging --remote \
  --command "SELECT * FROM firmware_releases ORDER BY created_at"
wrangler d1 execute trace-update-staging --remote \
  --command "SELECT * FROM firmware_channels"
# R2 目标键现状（预期 404 = 不存在；若 200 说明已占用，停止上报）
wrangler r2 object get trace-update-staging-releases/<对象键> --file <临时读回>
```
次数各 1，超时 60s。快照文件哈希登记进执行证据。

**步骤 1 —— 登记元数据构建（本地，不触网）**

```
node cloudflare/update-service/scripts/build-firmware-release-metadata.mjs \
  --assets-dir <admission>/.cache/p3-3-assets \
  --firmware-file e-track-at32f435-v3.2.1-full.etu \
  --release-tag mcu-e-track-at32f435-v3.2.1 \
  --run-id p3-3-fixture-30201 \
  --commit-sha <资产源镜像 freeze_commit> \
  --device-model e-track-at32f435 \
  --version-name 3.2.1 --version-code 30201 \
  --output <admission>/.cache/p3-3-assets/toy-firmware-metadata.json
```
- `--firmware-file` **必填**：脚本默认文件发现正则是 `\.(bin|hex|uf2|dfu)$`，
  不匹配 `.etu`（build-firmware-release-metadata.mjs:66-80）。
- `run_id` 用显式固定值 `p3-3-fixture-30201` / `p3-3-fixture-30202`（D1
  UNIQUE(run_id)，两份不得同值；不用真实 CI run id，避免冒充 CI 产物身份）。
- 次数 1；产物 JSON 留档。**注意：此脚本产出的是 v1 单文件元数据**；
  P4-2 后 register 要求 OTA-XC-RELEASE-METADATA v2（assets 数组）——届时
  若脚本未随 P4-2 升级，此步骤以 P4-2 提供的 v2 构建路径为准，本命令为
  现网 v1 链路的如实记录。
- **githubUrl 字段自动生成为
  `https://github.com/Eitan-S-23/Trace/releases/download/<releaseTag>/<fileName>`**
  ——该 Release 资产并不存在（见 §7 矛盾项），是否接受此字段值由用户
  裁定后本步骤方可执行。

**步骤 2 —— R2 上传（含读回校验）**

```
node cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs \
  --metadata <admission>/.cache/p3-3-assets/toy-firmware-metadata.json \
  --assets-dir <admission>/.cache/p3-3-assets \
  --bucket trace-update-staging-releases \
  --wrangler-cwd cloudflare/update-service/worker
```
- 脚本内部：本地 size/SHA 预检 → `wrangler r2 object put --remote`
  （immutable cache-control、attachment filename）→ **读回下载并复核
  size/SHA**（默认开启，`--skip-readback` 不用）。
- 次数 1（脚本内部 R2 重试默认 3 次，单次操作超时默认 300000ms，
  可 `--r2-retries/--r2-timeout-ms` 显式固定）；总超时申报 15 min。

**步骤 3 —— D1 candidate 登记（真网写入 #1）**

```
TRACE_UPDATE_SERVICE_URL=<Worker URL> TRACE_DEPLOY_TOKEN=<token> \
TRACE_REGISTER_RETRIES=3 TRACE_REGISTER_TIMEOUT_MS=30000 \
  node cloudflare/update-service/scripts/register-firmware-release.mjs \
  <admission>/.cache/p3-3-assets/toy-firmware-metadata.json
```
- `POST /api/ci/firmware/releases`（index.ts:65）；Bearer 验签
  （DEPLOY_TOKEN_SHA256）；`isFormalRelease` 必须 true（firmware.ts:157-159
  `FORMAL_RELEASE_REQUIRED` 403）；R2 key 策略校验（:584-589）；R2 head
  校验资产存在与 size/SHA（`validateFirmwareAsset`）；插入
  `firmware_releases` state=candidate + 自动建 firmware_channels 双行。
- 次数 1（脚本内部重试 3 次/单次 30s）；幂等语义：同 release_tag +
  同 run_id + 同 commit_sha 重放返回 idempotent（:169-171），不同值则
  `INVALID_PARAMETER` 拒绝（:186）。
- **P4-2 前置**：现网该端点只接受 v1 元数据；App 侧走不通的原因在
  latest 不在 register——但 v2 登记链（多资产行）必须随 P4-2 落地。

**步骤 4 —— firmware channel 指针激活（真网写入 #2，见 §6 时序）**

```
POST /api/admin/firmware/channels/stable/publish
  body: { releaseId: <步骤 3 返回的 releaseId> }
```
- 经 Access 保护的 admin（admin UI 按钮或带真实 Access 会话的 POST；
  admin/functions/api/admin/[[path]].ts:284-295）；**stable 需 owner 角色**
  （`requireRole(actor, channel === "stable" ? "owner" : "publisher")`）；
  CAS revision 防并发；VERSION_REGRESSION 检查（publishFirmwareRelease
  :770-879：目标 version_code 不得低于 channel 现指版本）。
- 次数 1（每份资产各 1 次 publish）；超时 30s；Access 会话由用户在
  执行时提供（本单不持有）。

**步骤 5 —— 只读终验（每份资产）**

```
GET /api/public/firmware/latest?appId=trace&deviceModel=e-track-at32f435&channel=stable
# 核对响应含目标 versionCode/fileName/sha256/sizeBytes（P4-2 后为 v2 结构）
# 下载链终验（App 实测前主机侧预检）：
GET /api/public/firmware/download?<latest 响应给出的 token 参数>
# 核对 X-Trace-Asset-Source: r2、Content-Length 与 sizeBytes 一致
```
次数各 1。App 端整链（latest 解析→token 下载→整包 SHA 校验→BLE 传输）
由 C-TOY/C-REAL-LOOP 实机判据执行，不在本写入单内。

### 5.2 激活时序（用户第 3 条原文要求：先 30201、toy 成功后再 30202）

```
步骤 0-3（toy 30201 登记 candidate）
→ 步骤 4（stable 指针 → 30201）
→ C-TOY-LOOP 实机闭环（合同判据，另行授权）
→ 【toy 闭环成功】后：步骤 0-3（真包 30202 登记 candidate）
→ 步骤 4（stable 指针 30201 → 30202）
→ C-REAL-LOOP 实机闭环（合同判据，另行授权）
```
- 真包的步骤 1-3 **不与 toy 同批执行**：30202 只在 toy 闭环成功后登记与
  激活。允许提前做真包的步骤 0 快照核对（只读）。
- channel 指针切换是唯一的"激活"动作：candidate 登记（步骤 3）后记录
  仍不可被 latest 查到（`current_release_id` 未指、download 报
  `ASSET_DISABLED` 410）；publish（步骤 4）后才对 App 可见。无任何直接
  SQL 改指针的动作。
- VERSION_REGRESSION 顺序性：30201→30202 递增，无回退。

### 5.3 清理范围（暂停状态下零待执行项；若本单曾解冻执行，验收轮结束后按本节方案清理，另行授权执行）

| 对象 | 清理动作 | 边界 |
| --- | --- | --- |
| D1 fixture 记录（30201/30202 两行） | `POST /api/admin/firmware/releases/<id>/disable`（owner 角色，admin [[path]].ts:297-306）置 disabled；触发器保证 disabled 不可被 channel 指向 | **不删除行**（现网 admin API 无 firmware delete；行保留即审计证据）；audit_logs 的 publish/disable 记录保留 |
| firmware_channels stable 指针还原 | **可执行方案（不以"将来自然前移"代替）**：现网 admin API 无 firmware channel 回退操作，唯一可执行路径是直接 D1 SQL——`wrangler d1 execute trace-update-staging --remote --command "UPDATE firmware_channels SET current_release_id = NULL, revision = revision + 1 WHERE current_release_id IN (<本单写入的 releaseId 清单>)"`（列名/WHERE 以步骤 0 写入前快照的实际行结构为准先核对；预期影响行数 ≤2；执行后 `SELECT * FROM firmware_channels` 复核与写入前快照逐列一致并落盘留证）。该 SQL 逐次报批执行，报批时附：精确命令、WHERE 限定、预期影响行数、写入前快照对照 | 仅还原本单 publish 触碰的指针；后续正式固件发布使指针前移只是客观时序后果，不构成清理方案的一部分 |
| R2 对象（两键） | `wrangler r2 object delete trace-update-staging-releases/<键>` | 仅删本单写入的两键；不触碰 bucket 内其他对象 |
| 写入前快照与执行证据 | **全部保留**（审计证据不删，用户第 3 条） | — |
| 本地资产实物 | `.cache/p3-3-assets/` 保留（受控资产唯一持有处，离线资产文档 §6） | — |

## 6. candidate→firmware channel 指针的合法录入方式（链路澄清）

用户第 3 条：「现有登记脚本创建的是 candidate，latest 读取的是 firmware
channel 指针」——与源码完全一致，链路为：

1. **candidate 创建**：仅步骤 3（`POST /api/ci/firmware/releases`，
   Bearer CI token）。脚本 `register-firmware-release.mjs` 是唯一合法入口；
   state 固定 'candidate'（firmware.ts:227），无 SQL 直插。
2. **channel 指针写入**：仅步骤 4（Access 保护 admin publish）。写入
   `firmware_channels.current_release_id` + revision CAS + audit_logs
   `publish_firmware` 审计行。**CI token 无权 publish**（publish 只走
   Access 会话 + 角色）——权限分离是现网设计，本单沿用。
3. **latest 读取**：`/api/public/firmware/latest` 按
   `(app_id, device_model, channel)` 查 `firmware_channels.current_release_id`
   → join `firmware_releases`（firmware.ts:312-326）。未 publish 的
   candidate 不可见。
4. **下载门禁**：`ensureFirmwareDownloadAllowed` 再校验 app/channel
   disable 与发布态（ASSET_DISABLED 410），token 验签前置——不旁路。

## 7. githubUrl 准入矛盾（用户裁定项，裁定前步骤 1 不得执行）

- register 强制校验 `githubUrl` 必须是
  `github.com/Eitan-S-23/Trace/releases/download/<releaseTag>/<fileName>`
  前缀 + 含 `/<releaseTag>/`（`assertImmutableGitHubAssetUrl`，
  firmware.ts:453,574-581），但**不验证该 Release/资产是否存在**（下载走
  R2，不走 githubUrl；该字段仅作溯源记录）。
- 两个互斥选项：
  - **不创建 GitHub Release** → githubUrl 指向不存在的 Release 资产，
    字段值事实虚构，与用户「不得伪造正式发布身份」冲突；
  - **创建 GitHub Release/tag**（`mcu-e-track-at32f435-v3.2.1/3.2.2`）→
    违反「不得借此创建未经授权的 tag/Release」。
- **本单不预设解法**，列为你裁定的选项：a) 接受不存在的 githubUrl 溯源
  字段（写明其为 fixture 占位）；b) 授权创建两个 MCU fixture Release
  （含资产上传）；c) P4-2 实现时调整 register 校验（属 P4-2 卡范围）。
  裁定前本单步骤 1-4 全部冻结。

**裁定回填（2026-09-13 第三轮裁定第 2 条）**：

- **不选 a**：不得填写指向不存在 Release URL 的 githubUrl 冒充溯源
  （v1 链路的数据完整性问题不做 fixture 占位妥协）。
- **不授权 b**：不为打通 v1 链路创建 Release/tag
  （`mcu-e-track-at32f435-v3.2.1` / `3.2.2` 两个 tag 均不创建）。
- **c 留给 P4-2**：register 校验的调整（含 githubUrl 字段语义、
  OTA-XC-RELEASE-METADATA v2 多资产登记）属 P4-2 任务卡范围，届时随
  worker v2 一并设计与审批。
- 实际效果：本单步骤 1-4 在 P4-2 落地前**永久冻结**（不止暂停）；P3-3
  的溯源需求由受控 v2 服务方案（本地 fixture 四元组 + SHA-256 身份链）
  承担，不依赖 GitHub Release URL。

## 8. 执行前置清单（全部满足才可开工；当前整体暂停，本表仅为解冻条件存档）

| # | 前置 | 状态 |
| --- | --- | --- |
| 1 | P4-2 固件 worker v2 实现并部署到目标实例（latest v2/register v2/token v2/D1 多资产），部署版本按 §2 核对回填 | 未开始（P4-2 DISPATCHABLE 未认领） |
| 2 | 用户裁定 githubUrl 矛盾（§7 三选项之一） | **已裁定（2026-09-13）**：不选 a、不授权 b、c 留给 P4-2（见 §7 裁定回填） |
| 3 | 本写入单获用户批准（含 §5.3 清理范围与时序 §5.2）+ **解除 B0-B4 暂停**（2026-09-13 第三轮裁定暂停中） | 暂停，待 P4-2 与用户解冻 |
| 4 | Cloudflare 账号/部署版本核对回填（§2） | 待执行前核对 |
| 5 | D1/R2 写入前快照（§5.1 步骤 0）完成且无占用冲突 | 待执行 |
| 6 | Access owner 会话（步骤 4 stable publish 需要）由用户在执行时提供 | 不持有；暂停状态下不申请、不传递 |
| 7 | BCB 恢复完成且终态核验通过——**P3-3 验收链已改走受控 v2 服务，本项不再是本单解冻条件，仅是云端激活后 C-TOY-LOOP 实机闭环的前置** | v4 方案已落盘待批（`P3-3-bcb-recovery-plan-2026-09-13-v4.md`，REC0-REC7） |

## 9. Cloudflare 账号操作规约（2026-09-13 第四轮裁定第 4 条回填）

适用于本单（B0-B4）与受控服务 HTTPS 路线 B（Cloudflare Named Tunnel，
服务文档 v2 §5）的一切 Cloudflare 账号操作；两者均未获批、未执行。

1. **当前路线不使用 Cloudflare**：受控服务 HTTPS 待批路线 A（自有域名 +
   Let's Encrypt DNS-01）不涉及 CF 账号；路线 B 未获批前不发起任何
   `wrangler`/`cloudflared` 账号类命令，不刷新或读取其 token，也不要求
   用户在聊天中提供任何凭据。
2. **路线 B 获批后的申报前置**：先说明具体目标账号、资源（tunnel/
   DNS zone/hostname）、域名和对外暴露范围（公网 URL、转发目标
   `localhost:<PORT>`、是否限源），由用户批准资源操作后，**先发起浏览器
   鉴权请求刷新本地登录**（`cloudflared tunnel login` /
   `wrangler login`），不得直接使用本地已有凭据开工。
3. **鉴权后身份核对**：核对实际 account ID 与目标资源归属
   （`wrangler whoami` / tunnel 列表 / zone 列表），排除旧环境 token
   覆盖新 OAuth 登录的情况（本地已有 cert/OAuth 配置时先核验其归属
   账号与目标资源是否一致，不一致则重新鉴权）。
4. **缓存身份与凭据边界**：不得沿用未经核验的缓存身份；不得全局删除
   其他账号凭据（`~/.cloudflared/cert.pem`、wrangler OAuth 配置等只按需
   核验指向，不批量清理、不删除无关条目）；不输出任何 token/cookie
   （包括日志、报告与聊天交付）。
5. **项目外写入预检**：PowerShell、Wrangler、cloudflared 的启动缓存、
   日志和认证文件（`~/.cloudflared/`、`%USERPROFILE%` 下 wrangler
   配置、浏览器鉴权落盘位置）均在项目根之外——任一写入前按全局
   「非项目目录写入边界」逐路径申报并获批；**浏览器鉴权不豁免项目外
   写入边界**。

## 10. 边界声明

- 本文档零云端写入、零部署、零真机操作、零代码改动；staging 仅有的两次
  公开 GET 探测（latest 返 86、firmware 缺参 400）在资产方案文档 §7 已
  如实记录。
- 本单所有命令/参数/行号引用均来自当前 admission worktree 源码
  （`cloudflare/update-service/`）；若 freeze_commit 后源码变化，须复核
  firmware.ts、admin [[path]].ts、三个 .mjs 脚本未变，否则本单升版。
- **批准本单 ≠ 解除 P4-2 前置**（§1）：在 worker v2 落地前，任何 D1/R2
  写入都只是为 App 走不通的 v1 链路准备数据。
- 与合同的关系：EXT-SERVICE external input 已改绑受控 v2 测试服务
  （`EXT-HTTP-TEST-SERVICE`，见服务文档 §7 与合同修订），**不再依赖本单**；
  C-APK-INSTALL 之后的 O2 观测依赖 endpoint 注入（已选 iii）+ 受控 v2
  服务部署（D1-D5 申请待批）。本单解冻前，云端链路对 P3-3 无阻塞项。
