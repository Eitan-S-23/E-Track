# P4-1 firmware-build.yml 正式发布链实施 Spec

task_id: P4-1

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P4-1` 行。本文件不得另行维护该状态。

## 目标

把现有单 bin 注册链扩展为冻结顺序要求的正式三资产链：finalize 最终 App、生成 full/patch/recovery、patch 逐字节自验、创建不可变 GitHub Release 资产、R2 上传/回读、生成 assets 数组 metadata 并注册 D1 ready 候选，同时保留 nightly 只构建不发布的隔离。

按 `OTA-DEC-016`，本卡在 P5 前的完成边界是实现及 staging rehearsal 资格，不是实际生产
发布。与 P4-4 共用一次获授权的演练原件；production promotion 留在 P5 通过及 owner/
environment 审批之后，不以生产 Release 作为进入 P5 的前置。

## 非目标

- 不修改 MCU/Flutter 产品实现或 binary contract。
- 不把 AC5 产物用于 OTA、CI release 或 recovery。
- 不在本卡实现 D1 migration/admin UI；只按共享注册合同调用负责卡提供的 API。
- 不绕过 environment 审批、Boot chain gate 或 vcode 单调检查。

## 前置依赖

- 看板显式依赖 `PRE-3`、`PRE-4`、`P0-2` 已完成。
- `P1-5` bootstrap 已完成，但 `OTA_BOOT_CHAIN_READY` 解锁仍受 P4-1 演练顺序约束。
- `P4-2` 必须先提供由 `OTA-XC-SCHEMA-FIXTURE` 约束的真实 register API、多资产 D1 model 和 ready 语义；依赖方向固定为 `P4-2 -> P4-1`。
- P4-1 与 `P3-5` 之间不建立自动依赖。资产命名、镜像摘要域和 rehearsal/production gate 的用户裁定已传播到并冻结在共享合同。
- P4-4 配置准备消费已交付 workflow 接线与目标环境接口，不要求先完成本卡的演练验收；两卡在配置可用后共用真实 rehearsal，避免相互等待完成态。

## 权威合同

- `OTA-XC-IMAGE-IDENTITY`
- `OTA-XC-ASSET-NAMING`
- `OTA-XC-RELEASE-CLI`
- `OTA-XC-BOOTSTRAP-BASE`
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

- 普通 build job 输出无凭据的未 finalize GCC App/Boot 四件套和版本信息，仅用于开发。两个受保护 release job 用同一 GCC/CMake recipe 和各自已批准的 OTA secret 生成同一 run 的 key-bound App/Boot 四件套，再制包；禁止拿普通开发 artifact 冒充已配置接收端 key。
- release job 默认取得上一正式版“最终 App bin”作为 patch 基版，并验证其 releaseTag/version/hash。首次发布的显式例外只能按 `OTA-XC-BOOTSTRAP-BASE` 获取独立核验、不可变归档的非正式基线；不得自动回退到 nightly、placeholder 或 `.etu` 反解结果。
- metadata builder 接收三类已验证资产和 release 身份，输出 `OTA-XC-RELEASE-METADATA`。
- uploader 对每个 asset 执行 immutable put/identical no-op/readback，再把 r2Verified metadata 交给 register API。
- 输出与退出码严格遵守 `OTA-XC-RELEASE-CLI`。

## 状态机与生命周期所有者

- GitHub Actions release job 是制包/发布编排 owner。
- `etu_pack.py` 是 finalize/full/patch 字节 owner，recovery helper 是 recovery 容器 owner。
- R2 uploader 是对象存在性/回读 owner；register API 是 draft/ready 原子门槛 owner。
- 任一步失败后 release 不得继续到下一不可逆步骤；重跑只通过幂等合同恢复。

### 编译与制包密钥接线

共用入口为 `.github/scripts/firmware-gcc-keyed-build.mjs --build-dir <项目内新目录>
--evidence-dir <独立的新证据目录> --version <精确版本>`。仅受保护且已过原 gate 的
rehearsal/production 步骤取得对应 OTA secret；不把云端或 GitHub 发布凭据交给编译器。
现有 GCC 13.3.Rel1、Release/Ninja、SOURCE_DATE_EPOCH=1786320000 和对象路径设置保持。

四个 `OTA_AES_KEY_1_WORDx` 由私有头文件注入实际 App `ota_keys.c` 编译命令，匹配的 Boot
同次构建；Boot 当前不消费 AES。私有头文件不进入证据目录，正常或已处理失败后删除。
keyed recipe 显式禁用编译缓存并核对实际 launcher，不允许 key 进入全局/远端 cache。
exclusive open 后立即记录所有权；取消/退出 trap 和独立 always cleanup 按精确
commit/run/attempt 校验自有路径，上传须先确认私有头文件不存在，不清理其他 run。
保留原始 bin/elf/hex/map、退出码/警告/错误、编译命令与自动派生的 `keyBinding`：
schemaVersion=1、keyId=1、source、keySha256、headerSha256、keySourceSha256。
这不是注册 schema 的新增字段，也不是另一个审批系统；批准来源仍是已受保护的 secret。

`firmware-release.mjs execute` 在网络前比对 build keyBinding 与 packer 同一 secret；
缺失、未知、开发来源、已知示例 key、编译/制包 fingerprint 不一致均退出 2。
编译失败或实际 App 命令未消费头文件退出 1，不生成合格 manifest。普通 CI 仅用
`--development` 显式运行同 recipe 的开发副本，并保留不可安装/不可发布标识；不能只
翻转源码 development 标记就宣称合格。实际编译证据必须来自 CI，不用宿主编译器替身代替。

现有首发归档是 raw patch 字节来源，不保证设备能以旧开发 key 解密新真实 key 包；
P3-5/P5 的设备 owner 负责实际 key provisioning/INFO 身份和 full 或精确新基版选择。
重新编译基版后 raw SHA 变化，不能继续冒用旧归档身份，不在本卡追加设备操作。

### 开发运行时资格检查

本入口只为验证原生 Wrangler 绑定能力，不生成目标制包或代替后续唯一 canonical rehearsal。
现有 workflow 的 `workflow_dispatch(check_bindings=true, publish=false, rehearsal=false)` 调用：

    node .github/scripts/firmware-bindings-check.mjs --output .cache/bindings-check/result.json

- job 使用 Linux 和 `firmware-rehearsal` environment，运行前必须已具备受保护的环境、经核验隔离的凭据及变量；禁止借 dispatch 自动创建无保护 environment。
- `FIRMWARE_REHEARSAL_BINDINGS_CHECK_COMMIT` 必须等于实际 `GITHUB_SHA`；repository、run/attempt、三个显式模式输入和 `OTA_BOOT_CHAIN_READY=false` 均须校验。它只批准固定源码的开发检查，不是首发 descriptor 或发布批准。
- 实际检查步骤仅接收 `FIRMWARE_REHEARSAL_CLOUDFLARE_ACCOUNT_ID`、`FIRMWARE_REHEARSAL_CLOUDFLARE_API_TOKEN`、`FIRMWARE_REHEARSAL_TRACE_UPDATE_SERVICE_URL` 三个 secret，以及对应 R2/D1 变量；安装依赖和普通 build/checks 不接触这些凭据。没有 AES key、deploy token、GitHub 写 token 或注册动作。
- 固定输入为已提交 `P4-1-r2-registration-qualification-2026-10-15/operations/verified-metadata.json` 的三个既有 synthetic 对象；通过原 uploader 的 `verifyStoredFirmwareAsset(metadata, fileName, bucket)` 复用全字节/长度/条件 ETag 校验，缺失即失败，绝不补传。
- `withFirmwareBucket` 保持原生 Wrangler 路径；Windows 10 在创建 runtime 目录前拒绝，Windows 11 按 build 22000 判别而非 kernel major。此检查不保证其他平台的全部先决条件，真实 runtime 资格仍须实测。
- Worker health/配置 GET 验证精确隔离目标，D1 只运行固定表的 count 和有界 channel SELECT 并比对前后结果；job/检查 step 分别限制 10/5 分钟，结束由原 adapter dispose。Wrangler remote bindings 会建立临时远端 preview session，所以只声明无 R2/D1 业务写请求，不能声明全局零远端写入或完整生产零副作用。

| 输入/结果 | 判定与负例 |
| --- | --- |
| 已批准提交、明确锁定 gate、隔离绑定且三对象完整 | 返回 `RUNTIME_BINDING_QUALIFICATION` 及实际读回摘要，rehearsal/独立验收仍未执行 |
| 普通 CI、缺配置、错提交、混合 publish/rehearsal/check | exit 2，在网络调用前失败；两个正式 job 也拒绝混合 check 模式 |
| 对象缺失、错误 metadata/字节、条件 GET 失败 | exit 1，不 PUT、不 register，不写成功结果 |
| Worker 绑定不符、查询失败、前后 D1 状态变化 | exit 1，保留失败日志，不报告资格通过 |

回归点是 `firmware-pipeline.host.test.ts` 的真实读回/SQLite 宿主检查和
`test_firmware_workflow.mjs` 的实际 Bash 门禁与 secret 隔离；宿主替身不冒充真实云端。
错误做法是重试 Windows workerd 崩溃、转存 provisioning token 或缺对象就上传；正确做法
是在已审且隔离的配置具备后执行一次有界原生 Linux 检查。

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
- 必要的 workflow 文档注释。用户委托的首发来源与演练桶修订仅限对应共享条款及消费记录，不修改历史冻结合同。正式执行须绑定获审的精确已提交分支 revision，不以整个 P4-1 先合并 main 为前置。

## 禁止修改与生产红线

- 禁止 release job 消费 AC5、旧 layout 或未 finalize bin。
- 禁止把 `OTA_BOOT_CHAIN_READY` 合并进 job `if` 造成静默 skip。
- 禁止移除 `firmware-production` environment 或人工审批。
- 禁止用 `--force` 覆盖不同 digest 的 R2/GitHub 正式资产。
- 禁止 nightly 建 Release、注册 D1 或接触生产 secrets。
- 禁止在共享合同发生未重新冻结的变更、`P4-2` 未完成，或 rehearsal/production 审批条件未满足时创建正式 release。
- 禁止建立临时 register stub、第二 schema 或把 D1 ready 排除出完成判据。

## 必须新增或调整的测试

- metadata/CLI：三资产正例、缺资产、重复 full/recovery、错误 base、非法名、摘要/长度错、稳定排序、退出码。
- patch：上一正式 finalized bin 来源校验、实际 apply、stdout 失败和逐字节 mismatch 负例。
- recovery：尾容器和剥尾/最终 fw_header 校验。
- workflow 静态：nightly 隔离、environment、gate 首步、secret 硬失败、三资产上传、步骤顺序。
- R2：不存在上传、相同 digest 幂等、不同 digest 碰撞拒绝、readback 失败。
- 注册：相同 metadata 重放和冲突不产生部分 ready。

## 完成判据

- 在共享冻结合同下的 rehearsal 路径生成 full/patch/recovery，所有 hash/size 与 metadata 一致。
- patch 对获准基版自验逐字节一致，recovery 验证通过；首发例外只改变来源资格，不降低三资产或真实字节要求。
- staging R2 三资产与本次产物/metadata 同字节，register ready/idempotency 和 rehearsal 前后 production D1/R2/channel/GitHub Release 零副作用均有证据；本阶段不创建 GitHub Release 或 prerelease。
- register 后 D1 release 达到 P4-2 的 ready 门槛；失败路径无 ready 残留。
- nightly/pull request 行为不回退，warning/error/退出码明确报告。

### P5 后 production promotion

此阶段不是本卡进入 P5 的前置，不能用 staging PASS 冒充已执行生产发布。

- 生产晋升仍须在 P5 通过后按 `OTA-XC-RELEASE-GATE` 重新构建并核对已批准 rehearsal 的三资产及 canonical metadata 摘要，完成 owner/environment 独立审批后才创建正式资产。
- 发布后核验 GitHub Release 精确含三类正式资产，数量/类型/名称符合 `OTA-XC-ASSET-NAMING`，R2 对象与 Release/metadata 同字节；实际 Release/R2 全字节摘要和长度须等于已批准目标，不只验证上传前的本地文件。
- 保留实际发布 run、审批、Release 资产清单、Release/R2 发布后 readback、metadata SHA 和注册 ready/idempotency 原件；任一失败按正式发布合同停止并记录，不能由发布前重建校验代替。

## 停止条件

- 镜像摘要、正式资产命名或 rehearsal/production gate 的共享条款发生未重新冻结的变更时停止正式发布动作。
- `P4-2` 的真实 schema/register/D1 ready 链未完成时停止，不建立临时 stub 或兼容双写。
- 无法取得可验证的上一正式 finalized App bin，且不存在按共享首发条款独立核验并获准的基线时，不得生成发布 patch 或用近似基版替代。
- Worker 仍只接受单资产或不能原子 ready 时停止注册，不做兼容双写。
- 需要降低 frozen finalize/patch/recovery 校验才能通过时停止。

## 后续证据

保存 workflow run/commit、environment 审批、全部 step 退出码、App/三资产/metadata SHA、上一正式基版来源、patch apply 比对、staging R2/D1 注册响应、冲突负例和生产零副作用快照。与 P4-4 共享原件并分别判定，不重做演练；后续生产晋升另保留其真实重建/审批/发布后资产清单及字节一致性记录。

## Luna 可自行决定

脚本拆分、verification summary 文件格式、Actions step 名称、项目内工作目录和测试 fixture 组织，只要产物/步骤/退出码合同不变。

## 阻断性决策

- 无未决规范决定。受保护的环境配置、隔离凭据、真实目标/descriptor 审批、运行时资格及正式执行型验收冻结仍是实际前置；不由条款冻结代替。已授权开发、自测和专属分支交付继续，实际资格引用看板 readiness 本行。
