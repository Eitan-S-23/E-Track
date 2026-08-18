# P4-2 D1 多资产模型与 latest 选包实施 Spec

task_id: P4-2

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P4-2` 行。本文件不得另行维护该状态。

## 目标

新增并回填 firmware 多资产 D1 模型，把 release 生命周期改为 draft/ready/disabled，改造 CI 注册为资产数组，令 latest 根据设备 currentImageSha 唯一选择匹配 patch 或回退 full，并保证 recovery 不自动分发、下载对象不可变。

## 非目标

- 不修改 MCU/Flutter wire 协议或制包算法。
- 不实现 admin 文案/撤回交互（P4-3），但提供其需要的原子 API/数据语义。
- 不自行决定 model 映射、摘要域、App 兼容、HTTP Range 或保留期限。
- 不通过 TypeScript 内存校验替代实际 D1/SQLite 约束。

## 前置依赖

- P0/P1/P2 的 package、header、R2 基础已存在。
- 本卡不依赖 `P4-1`。P4-2 拥有 `schemaVersion=2` 的 versioned schema fixture，并基于共享 release/register 合同先实现和验证 register/latest/D1。
- model、摘要、App 兼容、Range、保留策略、旧数据 identity 回填、Admin 幂等和 token v2 的用户裁定已传播到并冻结在共享合同。

## 权威合同

- `OTA-XC-INFO-MAPPING`
- `OTA-XC-CLOUD-QUERY-MAPPING`
- `OTA-XC-HTTP-LATEST`
- `OTA-XC-ASSET-SELECTION`
- `OTA-XC-HTTP-DOWNLOAD`
- `OTA-XC-HTTP-RESUME`
- `OTA-XC-HTTP-ERROR`
- `OTA-XC-HTTP-ADMIN`
- `OTA-XC-HTTP-REGISTER`
- `OTA-XC-RELEASE-METADATA`
- `OTA-XC-SCHEMA-FIXTURE`
- `OTA-XC-R2-UPLOAD`
- `OTA-XC-D1-RELEASE`
- `OTA-XC-D1-ASSET`
- `OTA-XC-D1-CHANNEL`
- `OTA-XC-D1-AUDIT`
- `OTA-XC-D1-STATE`
- `OTA-XC-D1-MIGRATION`
- `OTA-XC-D1-RETENTION`
- `OTA-XC-R2-IMMUTABILITY`
- `OTA-XC-IDEMPOTENCY`
- `OTA-XC-ADMIN-IDEMPOTENCY`
- `OTA-XC-UNKNOWN-FIELDS`

## 现有组件和代码入口

- `app/bluetooth_flutter_Trace/cloudflare/update-service/migrations/0003_firmware_releases.sql`：当前单资产 candidate/disabled schema。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/worker/src/firmware.ts`、`app/bluetooth_flutter_Trace/cloudflare/update-service/worker/src/types.ts`、`app/bluetooth_flutter_Trace/cloudflare/update-service/worker/src/errors.ts`：latest/download/register。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/worker/test/invariants.test.ts`、`app/bluetooth_flutter_Trace/cloudflare/update-service/worker/test/apply-migrations.ts`：现有 Worker/D1 测试入口。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/build-firmware-release-metadata.mjs`、`app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs`、`app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/register-firmware-release.mjs`。
- `admin/functions/api/admin/[[path]].ts`：channel publish 消费方。

## 输入输出与调用方向

- versioned fixture 的唯一来源是 `OTA-XC-RELEASE-METADATA` 与 `OTA-XC-HTTP-REGISTER`；不得从 `P4-1` 未完成产物反向定义 schema。
- CI register 输入完全遵守 `OTA-XC-RELEASE-METADATA`，未知字段/资产 kind 拒绝。
- Worker 先验证 release/asset 字段和每个 R2 对象，再以 D1 原子批次写 draft、assets、ready/audit。
- latest 输入为 typed query，输出为共享合同 schema v2；不得继续返回单资产平铺字段作为唯一规范格式。
- download 以 assetId+releaseId 查资产行，不再以 release.file_name 推导唯一 asset。
- owner admin 对固定 recovery-download endpoint 提交 release identity/reason，后端只为唯一 available recovery 返回限时 `purpose=admin-recovery` URL；该 URL 不进入 latest。

## 状态机与生命周期所有者

- register API 拥有 draft -> ready 转换。
- D1 unique/check/foreign key 是多资产不变量最终 owner。
- channel publish 只引用 ready release；latest 只读取 channel 当前 ready release。
- asset R2 state 与 release state 分离；某资产 archived 不自动把 release 变 ready/disabled，必须重新评估完整性。

## 错误、超时、重试、取消、恢复与幂等

- 注册所有校验失败必须无部分 ready；D1 batch 失败不得留下 channel 改动。
- 相同 metadata 重放返回幂等成功，不同 metadata 同 tag 返回冲突。
- latest 不完整时 fail closed；patch 不匹配自动 full，不返回错误 patch。
- signed download 失效、channel stop、asset/release 状态和 backend unavailable 按共享错误表；recovery token 只能由 owner admin 入口签发。
- migration/backfill 可重入；中断后重复运行不生成重复 asset。旧记录缺少 v2 必填 identity 时必须按 `OTA-XC-D1-MIGRATION` 停在不可逆写入和规范读切换之前。

## 允许修改范围

- `app/bluetooth_flutter_Trace/cloudflare/update-service/migrations/` 新 migration 和受控 backfill 脚本。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/worker/src/firmware.ts`、同目录 types/validation/errors/download 辅助模块和 `worker/test/`。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/` 下 firmware metadata/upload/register scripts。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/admin/functions/api/admin/[[path]].ts` 只实现共享合同固定的 recovery-download 后端入口及适配新表/ready gate 的必要读写，不做 P4-3 UI/channel mutation 语义扩展。
- 相关 README/测试 fixture。

## 禁止修改与生产红线

- 禁止改写已应用的 `0003` 作为唯一迁移；必须新增向前 migration。
- 禁止让 SQLite NULL 绕过 full/patch 唯一性。
- 禁止 ready release 缺 full、存在重复 full 或引用未验证 R2 对象。
- 禁止 latest 自动返回 recovery。
- 禁止偏离 `OTA-XC-IMAGE-IDENTITY`，同时匹配 raw/header 两种 SHA 或用 asset digest 猜测目标镜像身份。
- 禁止回填时把无法验证的旧记录默认为 ready。
- 禁止依赖 `P4-1`、建立 register stub、手改 D1 或使用任意 JSON 作为规范 fixture。

## 必须新增或调整的测试

- 实际 SQL：第二个 full 拒绝、同基版第二个 patch 拒绝、非法 kind/base 组合拒绝、缺 full ready 拒绝。
- migration：按 `OTA-XC-D1-MIGRATION` 验证版本化 manifest、旧单资产回填 full、published 安全映射 ready、disabled 保留、缺字段/不可验证 legacy 隔离、重复回填幂等，以及 `firmware_admin_idempotency_tombstones` 的唯一键、永久保留和清理前先落 tombstone。
- fixture/register：`schemaVersion=2` 的 full/patch/recovery 正例、R2 size/digest mismatch、相同 canonical metadata 重放、同 releaseTag 不同 metadata 冲突、非法/未知字段拒绝、batch 失败无部分状态。
- latest：patch match、full fallback、no update、not-ready、重复/缺 full、recovery hidden、兼容阻断。
- download：assetId/purpose 绑定、长度/摘要头、停发/撤回/archived、Range 正反例按共享合同；token v2 query/canonical/v1 切换做正反例；owner recovery-download 覆盖首次成功、非 ready/disabled/archived、缺失/重复/不可用 recovery，以及 Admin 幂等重放/冲突/过期边界和 tombstone/清理竞态。
- admin channel 只能发布 ready，CAS/版本回退保护不回退。

## 完成判据

- 新 migration 在空库和含旧 firmware 数据的库均可复现执行。
- 三项 R8 SQL 负例由数据库实际拒绝，不依赖应用预检查。
- latest 三场景和错误场景全部通过，返回字段与共享合同一致。
- recovery 只能通过 `OTA-XC-HTTP-ADMIN` 固定的 owner recovery-download 入口取得 `purpose=admin-recovery` URL，public latest 永不返回。
- Worker typecheck/test、migration test 和脚本 test 全部通过。

## 停止条件

- 任一受影响共享条款发生未重新冻结的变更且 schema/API 必须选择唯一语义时停止该部分。
- D1 运行环境无法提供所需原子性时先给出最小复现和替代设计评审，不用多次非原子写冒充事务。
- 发现现有数据缺少 `OTA-XC-D1-MIGRATION` 所列任一权威字段来源时 fail closed，保持 legacy 隔离并报告精确记录；不得以 asset digest、0、空串或环境默认值补齐。
- 需要双写两套长期 schema 才能上线时停止并提交架构复核，不得新增第二真相源。

## 后续证据

保存 migration 前后抽样、实际 SQL 失败输出、D1 schema dump、Worker tests、latest/download fixture、R2 HEAD/readback、register/audit 结果和幂等/冲突日志。

## Luna 可自行决定

新 migration 编号、Worker 内部 repository/service 拆分、查询索引、测试 helper 和 backfill 批大小，只要 D1/HTTP 合同和原子性不变。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
