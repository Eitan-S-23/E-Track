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
- rehearsal 与 production 的隔离、证据、独立 reviewer、人工 gate 和 production 审批已传播到 `OTA-XC-RELEASE-GATE` 与 `OTA-XC-SECRETS`，但仍须独立复核。
- 用户/owner 可操作 GitHub environment、repository secrets/variables、Cloudflare token/bucket/Worker secrets。

## 权威合同

- `OTA-XC-SECRETS`
- `OTA-XC-RELEASE-GATE`
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
- workflow 读取 GitHub secrets/variables，Wrangler 调 Cloudflare，register client 调 Worker。
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
- P4-1 rehearsal/正式 run 按共享候选合同区分 staging/rehearsal 与 production，并验证 gate 不可绕过。

## 完成判据

- `OTA-XC-SECRETS` 中每项配置均存在于正确平台和作用域，证据不含明文。
- `firmware-production` 至少有独立 reviewer，正式 job 确实等待审批。
- P4-1 能通过 R2 上传/回读和 Worker 注册，且失败负例不泄露 secret。
- 配置 owner、轮换方式和应急撤销路径有记录。

## 停止条件

- `OTA-XC-RELEASE-GATE` 或 `OTA-XC-SECRETS` 尚未独立复核时，不执行 production 解锁或生产验证。
- 用户/owner 未授权平台配置、token 创建或 environment 修改时停止。
- 唯一可行方案要求输出 secret 明文或授予不必要全账户权限时停止。
- P4-1/P4-2 实现尚未满足幂等/不可变合同，不进行生产验证。

## 后续证据

保存配置名称/作用域检查、脱敏权限摘要、environment reviewer 配置、Actions run/审批事件、R2/Worker 成功响应 requestId 和无泄露日志扫描。

## Luna 可自行决定

脱敏检查脚本、平台配置核对表和证据截图裁剪方式；任何实际 secret 值、权限扩大和 reviewer 选择必须由用户/owner 决定。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
