# P4-3 admin 撤回语义与运营开关实施 Spec

task_id: P4-3

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P4-3` 行。本文件不得另行维护该状态。

## 目标

把 firmware admin 的“rollback”改为准确的“retract/撤回”语义，增加发布/撤回 reason、channel latest/download 停发开关、ready gate、CAS 原子性和审计；UI 必须明确已升级设备不会降级，救治方式是发布更高 vcode。

## 非目标

- 不实现设备降级、强制回滚或修改 MCU 防降级规则。
- 不修改制包、Flutter transport 或 public binary schema。
- 不自行决定 patch 基版/旧资产保留期限。
- 不把 release `disabled` 与 channel `retract` 混为同一状态。

## 前置依赖

- P4-2 多资产和 ready release 语义已实现。
- 角色/Access/CAS/audit 基础沿用现有 admin。
- 资产保留、Admin release-action 幂等和 token v2 的用户裁定已传播到共享合同；只有候选条款独立复核后才能实施自动清理或安全能力。

## 权威合同

- `OTA-XC-D1-STATE`
- `OTA-XC-D1-CHANNEL`
- `OTA-XC-D1-AUDIT`
- `OTA-XC-D1-RETENTION`
- `OTA-XC-HTTP-ADMIN`
- `OTA-XC-HTTP-DOWNLOAD`
- `OTA-XC-ADMIN-RETRACT`
- `OTA-XC-ADMIN-STOP`
- `OTA-XC-IDEMPOTENCY`
- `OTA-XC-ADMIN-IDEMPOTENCY`
- `OTA-XC-HTTP-ERROR`
- `OTA-XC-R2-IMMUTABILITY`
- `OTA-XC-SECURITY`

## 现有组件和代码入口

- `app/bluetooth_flutter_Trace/cloudflare/update-service/admin/functions/api/admin/[[path]].ts`：firmware list/channel publish/disable、当前 `rollback` flag 和 CAS。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/admin/public/index.html`：MCU firmware UI、双语文案、确认弹窗和操作请求。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/migrations/0003_firmware_releases.sql`：当前 `last_action=rollback` 和 stop 字段。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/worker/src/firmware.ts`：latest/download 对 stop/disabled/channel pointer 的消费。
- Worker/admin typecheck 和 invariants tests。

## 输入输出与调用方向

- publish/retract/stop/resume 必须使用 `OTA-XC-HTTP-ADMIN` 固定的 method/path、请求 JSON、成功包络和鉴权错误，不得另建同义 endpoint。
- publish/retract/stop/resume 请求必须携带 non-empty reason 和 expectedRevision。
- retract 必须指定目标 ready release，更新 channel pointer；不得改设备、不得把目标 release 标为“已回滚”。
- stop_latest 影响新 latest 查询；stop_downloads 也阻断已签发 URL 的后续下载。
- release disable 必须使用固定 endpoint、owner、reason 和原子 audit；仍被 channel 引用时不得改 release state。
- admin response 返回新 revision/requestId；audit 保存 before/after/reason/actor/action。

## 状态机与生命周期所有者

- channel pointer/revision/stop flags 由 admin API 原子更新。
- release state 由 P4-2 model 管理；retract 不改变 release state。
- UI 只发用户选择和 expectedRevision，不在浏览器本地推断最终 channel 状态；操作后重新读取。
- stable publish/retract 继续要求 owner，beta 按现有角色规则。

## 错误、超时、重试、取消、恢复与幂等

- reason 缺失/空白返回 400 `INVALID_PARAMETER`；publish/retract 的 draft、archived、disabled 分别返回 409 `RELEASE_NOT_READY`、410 `RELEASE_ARCHIVED`、410 `RELEASE_DISABLED`，disable 目标仍被 channel 引用返回 409 `RELEASE_IN_USE`。
- revision 变化返回 409 CAS_CONFLICT，UI 刷新后让用户重新确认，不自动重放。
- stop/resume 同值请求可定义为幂等成功，但 audit 不能伪造 revision 变化。
- release disable/recovery-download 不得用 requestId、reason 或当前状态猜测重放；网络未知结果后的行为只能按最终 release-action 幂等合同实现。
- confirm 取消无副作用；网络未知结果后先读取 channel revision，不能直接重试写。
- retract 到低 vcode 只改变未升级设备的可见版本，UI 必须显示能力边界。

## 允许修改范围

- admin function、`admin/public/index.html`、admin type definitions/tests。
- P4-2 migration/Worker 中适配 action/reason/stop 的必要字段和读取逻辑。
- Worker/admin 文档和接口测试。

## 禁止修改与生产红线

- 禁止在 UI/API 使用“设备回滚成功”“已升级设备降级”等误导文案。
- 禁止绕过 expectedRevision、ready gate、role 或 reason。
- 禁止撤回时删除/覆盖 R2 资产或更改 release version/hash。
- 禁止让 stop_latest 自动放开 download，或 stop_downloads 只影响新 URL 而不校验旧 URL。
- 禁止在 `OTA-XC-D1-RETENTION` 与 `OTA-XC-R2-IMMUTABILITY` 尚未独立复核时新增自动删除策略。

## 必须新增或调整的测试

- 固定 endpoint/method、未知字段、成功 JSON、Access/角色/origin/CSRF 分类错误和 requestId 传播。
- publish/retract reason 必填、角色、ready gate、version regression、CAS 冲突和 audit。
- retract 后 latest 返回旧 ready release，但已升级设备 current vcode 导致 no update，不出现降级包。
- stop_latest/resume_latest、stop_downloads/resume_downloads 及已签 URL 下载阻断。
- 固定 release disable endpoint 的请求/响应、owner/reason、channel 引用保护和原子 audit；按 `OTA-XC-ADMIN-IDEMPOTENCY` 覆盖 same-key replay、different-fingerprint conflict、保存期边界和结果清理先后不变的 tombstone 竞态；retract 不改变 release state/R2。
- UI 双语文案、确认内容、错误提示、revision 刷新和截图验收。

## 完成判据

- API、注释、UI、确认弹窗和 audit 全部使用 retract/撤回语义。
- 发布/撤回/停发均有 reason、CAS、角色和原子证据。
- public latest/download 对开关行为与共享合同一致。
- admin 演练截图和接口测试覆盖 stable/beta、成功/冲突/取消。

## 停止条件

- P4-2 ready/channel model 未完成时停止，不在旧单资产 schema 上叠长期兼容逻辑。
- 保留/删除共享候选条款尚未独立复核时停止任何自动清理、保留数量或物理删除实现。
- 发现当前 Access 角色无法满足 stable owner 审批时报告治理缺口，不降低权限。
- 需要设备降级才能实现“撤回”时说明产品误解并停止。

## 后续证据

保存 API request/response（脱敏）、D1 before/after/revision、audit 记录、latest/download 验证、角色负例、双语 UI 截图和被撤回设备行为说明。

## Luna 可自行决定

UI 控件布局、reason 输入组件、handler/service 内部命名和 audit helper，只要固定 HTTP endpoint、外部语义、角色和原子性不变。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
