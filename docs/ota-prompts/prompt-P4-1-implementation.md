# P4-1 firmware-build.yml 正式发布链实施 Spec

task_id: P4-1

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P4-1` 行。本文件不得另行维护该状态。

## 目标

把现有单 bin 注册链扩展为冻结顺序要求的正式三资产链：finalize 最终 App、生成 full/patch/recovery、patch 逐字节自验、创建不可变 GitHub Release 资产、R2 上传/回读、生成 assets 数组 metadata 并注册 D1 ready 候选，同时保留 nightly 只构建不发布的隔离。

## 非目标

- 不修改 MCU/Flutter 产品实现或 binary contract。
- 不把 AC5 产物用于 OTA、CI release 或 recovery。
- 不在本卡实现 D1 migration/admin UI；只按共享注册合同调用负责卡提供的 API。
- 不绕过 environment 审批、Boot chain gate 或 vcode 单调检查。

## 前置依赖

- 看板显式依赖 `PRE-3`、`PRE-4`、`P0-2` 已完成。
- `P1-5` bootstrap 已完成，但 `OTA_BOOT_CHAIN_READY` 解锁仍受 P4-1 演练顺序约束。
- `P4-2` 必须先提供由 `OTA-XC-SCHEMA-FIXTURE` 约束的真实 register API、多资产 D1 model 和 ready 语义；依赖方向固定为 `P4-2 -> P4-1`。
- P4-1 与 `P3-5` 之间不建立自动依赖。资产命名、镜像摘要域和 rehearsal/production gate 的用户裁定已传播到共享合同，但仍须独立复核。

## 权威合同

- `OTA-XC-IMAGE-IDENTITY`
- `OTA-XC-ASSET-NAMING`
- `OTA-XC-RELEASE-CLI`
- `OTA-XC-RELEASE-METADATA`
- `OTA-XC-SCHEMA-FIXTURE`
- `OTA-XC-R2-UPLOAD`
- `OTA-XC-HTTP-REGISTER`
- `OTA-XC-RELEASE-GATE`
- `OTA-XC-R2-IMMUTABILITY`
- `OTA-XC-IDEMPOTENCY`
- `OTA-XC-RETRY-POLICY`
- `OTA-XC-SECURITY`
- `OTA-XC-SECRETS`
- `PLAN-OTA.md` §6.1

## 现有组件和代码入口

- `.github/workflows/firmware-build.yml`：GCC build、placeholder 检查、finalize、单 bin Release/R2/register。
- `Tools/etu_pack.py`、`Tools/etu_unpack.py`：finalize/full/patch 和验证。
- `Tools/jlink/prepare-bootstrap-app.py` 或 recovery helper：尾容器生成/校验入口。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/build-firmware-release-metadata.mjs`：当前单资产 metadata。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/upload-firmware-r2-asset.mjs`、`app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/register-firmware-release.mjs`：当前单资产上传/注册。
- Worker register API 和 D1 model 的负责卡实现。

## 输入输出与调用方向

- build job 输出未 finalize GCC App/Boot 四件套和版本信息；release job 下载同一 run artifact。
- release job 取得上一正式版“最终 App bin”作为 patch 基版，并验证其 releaseTag/version/hash，不得使用 nightly、placeholder 或 `.etu` 反解结果代替权威基版。
- metadata builder 接收三类已验证资产和 release 身份，输出 `OTA-XC-RELEASE-METADATA`。
- uploader 对每个 asset 执行 immutable put/identical no-op/readback，再把 r2Verified metadata 交给 register API。
- 输出与退出码严格遵守 `OTA-XC-RELEASE-CLI`。

## 状态机与生命周期所有者

- GitHub Actions release job 是制包/发布编排 owner。
- `etu_pack.py` 是 finalize/full/patch 字节 owner，recovery helper 是 recovery 容器 owner。
- R2 uploader 是对象存在性/回读 owner；register API 是 draft/ready 原子门槛 owner。
- 任一步失败后 release 不得继续到下一不可逆步骤；重跑只通过幂等合同恢复。

## 错误、超时、重试、取消、恢复与幂等

- 缺 secret/config 返回配置错误并硬失败，禁止使用开发 AES key 或 staging bucket 默认值。
- patch 自验必须解包/应用后与 finalized App 逐字节比较；工具返回 0 但 stdout/比对失败仍为失败。
- 同 releaseTag/commit/metadata 重跑不得覆盖不同字节的 GitHub/R2 asset。
- 网络 retry 仅按共享合同；4xx/409 不盲重试。
- workflow 被取消时不得留下 ready release 指向不完整资产；下次重跑必须先核对已有对象。

## 允许修改范围

- `.github/workflows/firmware-build.yml`。
- `Tools/etu_pack.py`、recovery/验证 helper，只做正式链所需的可复用 CLI 增量。
- `app/bluetooth_flutter_Trace/cloudflare/update-service/scripts/` 的 firmware metadata/upload/register 脚本。
- `.github/scripts/` 和 `tests/ota/` 下发布链单元/静态测试。
- 必要的 workflow 文档注释，但不修改冻结合同。

## 禁止修改与生产红线

- 禁止 release job 消费 AC5、旧 layout 或未 finalize bin。
- 禁止把 `OTA_BOOT_CHAIN_READY` 合并进 job `if` 造成静默 skip。
- 禁止移除 `firmware-production` environment 或人工审批。
- 禁止用 `--force` 覆盖不同 digest 的 R2/GitHub 正式资产。
- 禁止 nightly 建 Release、注册 D1 或接触生产 secrets。
- 禁止在共享候选合同未独立复核、`P4-2` 未完成，或 rehearsal/production 审批条件未满足时创建正式 release。
- 禁止建立临时 register stub、第二 schema 或把 D1 ready 排除出完成判据。

## 必须新增或调整的测试

- metadata/CLI：三资产正例、缺资产、重复 full/recovery、错误 base、非法名、摘要/长度错、稳定排序、退出码。
- patch：上一正式 finalized bin 来源校验、实际 apply、stdout 失败和逐字节 mismatch 负例。
- recovery：尾容器和剥尾/最终 fw_header 校验。
- workflow 静态：nightly 隔离、environment、gate 首步、secret 硬失败、三资产上传、步骤顺序。
- R2：不存在上传、相同 digest 幂等、不同 digest 碰撞拒绝、readback 失败。
- 注册：相同 metadata 重放和冲突不产生部分 ready。

## 完成判据

- 共享合同独立复核后的 rehearsal 路径生成 full/patch/recovery，所有 hash/size 与 metadata 一致。
- patch 对上一正式最终 App 自验逐字节一致，recovery 验证通过。
- GitHub Release 精确含三类正式资产，R2 对象与 Release/metadata 同字节。
- register 后 D1 release 达到 P4-2 的 ready 门槛；失败路径无 ready 残留。
- nightly/pull request 行为不回退，warning/error/退出码明确报告。

## 停止条件

- 镜像摘要、正式资产命名或 rehearsal/production gate 的共享候选条款尚未独立复核时停止正式发布动作。
- `P4-2` 的真实 schema/register/D1 ready 链未完成时停止，不建立临时 stub 或兼容双写。
- 无法取得可验证的上一正式 finalized App bin 时不得生成 patch 或用近似基版替代。
- Worker 仍只接受单资产或不能原子 ready 时停止注册，不做兼容双写。
- 需要降低 frozen finalize/patch/recovery 校验才能通过时停止。

## 后续证据

保存 workflow run/commit、environment 审批、全部 step 退出码、App/三资产/metadata SHA、上一正式基版来源、patch apply 比对、GitHub/R2 列表、D1 注册响应和冲突负例。

## Luna 可自行决定

脚本拆分、verification summary 文件格式、Actions step 名称、项目内工作目录和测试 fixture 组织，只要产物/步骤/退出码合同不变。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
