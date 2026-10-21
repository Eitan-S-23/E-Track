# P4-4 Secrets 与 environment 配置集成 Spec

task_id: P4-4

## 任务类型

`INTEGRATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P4-4` 行。本文件不得另行维护该状态。本卡包含必须由用户/仓库 owner 完成的 GitHub/Cloudflare 配置。

## 目标

在 GitHub repository/environment 与 Cloudflare 中配置正式发布所需 secrets、variables、R2 bucket 和审批人，验证 P4-1 发布链能够在不泄露凭据的前提下完成授权、上传和注册。

## 非目标

- 不生成、展示、导出或提交 secret 明文。
- 不降低 token 权限范围来换取“先跑通”。
- 不实现 P4-1/P4-2/P4-3 产品代码。
- 不自行绕过 `OTA_BOOT_CHAIN_READY` 或 environment 审批。

## 前置依赖

- P4-1 workflow 已按共享 secret 名称和硬失败规则接线。
- P4-2 Worker/R2 endpoint 已部署到目标环境。
- 以上是配置准备所需的已实现接线与环境，不是要求 P4-1 已完成验收。按 `OTA-DEC-016`，两卡共用一次 staging rehearsal，分别判定发布链与配置要求，不相互等待完成态。
- rehearsal 与 production 的隔离、证据、独立 reviewer、人工 gate 和 production 审批已传播到并冻结在 `OTA-XC-RELEASE-GATE` 与 `OTA-XC-SECRETS`。
- 现有账户专用 CI Token 按 `OTA-XC-SECRETS` 的 `P41-CF-CREDENTIAL-02` 用户例外消费；复用测试资源，不重复开户/订阅，不转存本地 provisioning token，不把同账户能力边界或配置回执冒充硬权限隔离及演练通过。本接口修订不启动本卡。
- 用户/owner 可操作 GitHub environment、repository secrets/variables、Cloudflare token/bucket/Worker secrets。

## 权威合同

- `OTA-XC-SECRETS`
- `OTA-XC-RELEASE-GATE`
- `OTA-XC-BOOTSTRAP-BASE`
- `OTA-XC-SECURITY`
- `OTA-XC-R2-IMMUTABILITY`
- `OTA-XC-RETRY-POLICY`

## 现有组件和代码入口

- `.github/workflows/firmware-build.yml` 的 Cloudflare config/gate/release job。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/worker/wrangler.jsonc` 和环境绑定。
- GitHub environment `firmware-production`、repository secrets/variables。
- Cloudflare R2 bucket、API token、Worker `DEPLOY_TOKEN_SHA256` 和 download HMAC secrets。

## 输入输出与调用方向

- 用户输入 secret/variable 到平台配置界面；agent 只验证名称存在性、权限结果和工作流脱敏输出。
- 2026-10-19 P44-CREDENTIAL-01 owner 裁定：workflow 使用标准 S3 SDK 和独立桶限定凭据，固定鉴权只读预检及 register client 调既有 Worker；不再要求 CLOUDFLARE_API_TOKEN 或向客户端暴露 D1 选择参数。当前接线以 OTA-XC-SECRETS/OTA-XC-R2-UPLOAD 的修订为准，旧冻结包不改写。
- check_bindings 的旧存储 fixture 与单调预检身份分别绑定。仅资格检查新增的 firmware-rehearsal variables `FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_PATH` / `FIRMWARE_REHEARSAL_BINDINGS_CHECK_METADATA_SHA256` 由 reviewer 选定真实受审候选或当前 canonical registration；原始 SHA、检查源码及原发布身份都须保存。它们不是生产发布必需变量，也不批准新 rehearsal 或跳过单调性。
- 首发配置须消费 `OTA-XC-BOOTSTRAP-BASE` 的非正式 descriptor/审批摘要，演练桶改名不能让旧 Trace 桶进入 production；不得自行回退或修改旧服务。接口允许按精确已提交的待合并分支审查和冻结，不要求整个 P4-1 先合并 main。这只是交付接口传播，不启动本卡或授予配置操作。
- 输出为平台侧配置清单（只含名称/是否存在/权限范围描述）、environment 审批证据和 P4-1 run 结果。

## 状态机与生命周期所有者

- GitHub/Cloudflare owner 拥有 secret 值和轮换。
- release job 只消费，不持久化或回显。
- environment reviewer 拥有人工批准；agent 不模拟批准人。
- key/token 轮换后必须用新 run 验证，旧 run 不能证明当前配置。

## 错误、超时、重试、取消、恢复与幂等

- 任一必需配置缺失时 workflow 首个相关步骤硬失败并仅报告名称。
- 权限不足、bucket 不存在、register 401/403 必须停止，不扩大 token 到全账户权限作为默认修复。
- 用户取消审批无副作用；重新批准触发新 job/run。
- 相同配置重复运行依赖 P4-1/P4-2 幂等规则，不覆盖不同资产。

## 允许修改范围

- GitHub repository/environment 和 Cloudflare 目标资源的用户授权配置。
- 若名称接线错误，可修改 `.github/workflows/firmware-build.yml` 或相关部署文档/测试，但不得记录值。
- 项目内 `docs/ota-exec-notes/P4-4-*.md` 只保存脱敏证据。

## 禁止修改与生产红线

- 禁止把 secret 写入仓库、Actions artifact、日志、截图可见区或聊天回复。
- 禁止使用 vendor 示例 AES key 走正式链。
- 禁止把 staging bucket 默认值当 production 配置。
- 禁止移除 environment reviewer、把 secret 改为普通 variable 或让 fork PR 读取 production secret。
- 禁止执行未获用户授权的账户级配置变更。

## 必须新增或调整的测试

- workflow 静态检查所有名称、secret/variable 类型、environment 声明和缺失硬失败。
- 负例：逐项缺失/错误 token/bucket/URL，日志无值泄露。
- 权限最小化验证：R2 token 只具有所需 bucket/operation，deploy token 只接受目标 Worker。
- environment 审批前 job 等待，拒绝/批准行为可见。
- P4-1 rehearsal 与配置要求共用原件，验证 staging 隔离和 gate 不可绕过；不得为了完成本卡提前发起 production 发布。

## 完成判据

- `OTA-XC-SECRETS` 中每项配置均存在于正确平台和作用域，证据不含明文。
- `firmware-production` 至少有独立 reviewer，workflow 接线与平台审批配置可核验；本阶段由 rehearsal 验证等待/拒绝行为，production job 的实际审批与执行留在 P5 后晋升时留证，不能写成已执行。
- P4-1 在隔离 staging 通过 R2 上传/回读和 Worker 注册，且失败负例不泄露 secret，生产资源前后快照证明零副作用。
- 配置 owner、轮换方式和应急撤销路径有记录。
- 本卡 P5 前完成仅表示配置/演练资格，不授权 `OTA_BOOT_CHAIN_READY=true`。P5 通过、独立 reviewer 与 owner/environment 审批及生产重建摘要一致性要求均保留。

## 停止条件

- `OTA-XC-RELEASE-GATE` 或 `OTA-XC-SECRETS` 发生未重新冻结的变更时，不执行 production 解锁或生产验证。
- 用户/owner 未授权平台配置、token 创建或 environment 修改时停止。
- 唯一可行方案要求输出 secret 明文或授予不必要全账户权限时停止。
- P4-1/P4-2 实现尚未满足幂等/不可变合同，不进行生产验证。

## 后续证据

保存配置名称/作用域检查、脱敏权限摘要、environment reviewer 配置、Actions run/审批事件、R2/Worker 成功响应 requestId 和无泄露日志扫描。

## Luna 可自行决定

脱敏检查脚本、平台配置核对表和证据截图裁剪方式；任何实际 secret 值、权限扩大和 reviewer 选择必须由用户/owner 决定。

## 阻断性决策

- 无未决规范决定。目标环境、最小权限凭据、独立审批与共享 rehearsal 原件仍须实际具备；条款冻结不启动本卡，也不授予配置操作。具体资格只引用看板 readiness 本行。
