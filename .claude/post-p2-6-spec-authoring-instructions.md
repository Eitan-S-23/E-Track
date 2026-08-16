# 本地元提示词：一次性完善 P2-6 后续 OTA 任务的 Luna-ready Spec 体系

> 用途：驱动一次性的后续 Spec 编写会话。本文不是任务卡、接口合同或验收标准，不纳入正式规范真相源。

你是本轮独立 Spec 设计方。请基于当前仓库，一次性完成 P2-6 之后所有任务的任务盘点、共享跨系统合同、逐卡派单 Spec 草案、决策登记和 readiness 矩阵。

本轮只完善稳定接口、实现边界和验收范围，不提前实现产品功能，也不强行把所有任务标记为 READY。

## 0. 成功标准

本轮成功标准是：

1. P2-6 后所有任务均按看板实际顺序和依赖被准确盘点。
2. MCU、Flutter、HTTP、D1、发布工具之间的稳定规则具有唯一规范来源。
3. 每张任务卡都有派单或验收 Spec 草案，或有明确的阻断原因。
4. Luna 不需要自行发明跨层字段、协议、状态机、错误语义或产品规则。
5. 所有未决问题均被正确分类和登记。
6. 不修改冻结合同，不改变任务结构，不依赖未提交的相关实现。
7. 新增或修改的规范只作为待独立复核的候选稿。

允许任务保持 NEEDS_DECISION、DEFERRED_ACCEPTANCE 或 BLOCKED_BY_DEPENDENCY。不得为了追求全部 READY 而自行创造产品规则。

## 1. 开始前检查

活动项目根目录固定为：

D:\github\my\E-Track

开始编辑前必须：

1. 阅读根目录 AGENTS.md。
2. 确认项目根目录、当前分支和 git status。
3. 阅读 PLAN-OTA-EXEC.md 中 P2-6 的明确状态。
4. 确认 docs/ota-prompts/prompt-P2-6-implementation.md 已按仓库规则冻结。
5. 确认 P2-6 Spec 最终要求的 Acceptance Governance 结果已经通过。
6. 确认不存在会改变 P2-6 Spec 基线的语义相关未提交修改。
7. 记录开始前全部已跟踪修改、未跟踪文件和相关忽略目录产物。

本任务所称“P2-6 Spec 基线已收口”只要求同时满足：

- P2-6 实现提示词已经冻结。
- 最终要求的治理检查已经通过。
- 不存在污染该 Spec 基线的语义相关脏修改。

P2-6 产品实现卡仍为“待办”不构成本任务阻断。尚未创建实现完成后才需要冻结的 docs/acceptance-contracts/P2-6-v1.contract.json，也不构成本任务阻断。不得把“P2-6 Spec 基线收口”误读为“P2-6 产品实现或正式验收已经完成”。

不得仅凭历史会话、文件存在或任务编号推测上述三项已经满足。

若无法客观确认上述三项 Spec 基线条件：

- 停止所有文件编辑。
- 可以继续只读盘点。
- 输出缺失依据和阻断报告。
- 不得把后续 Spec 叠加到未收口基线上。

## 2. 脏工作区处理

不能只按“是否与写入目标文件重叠”判断冲突。

如果存在未提交的以下语义相关修改，应视为 Spec 基线冲突：

- MCU OTA、Boot、BLE 或固件元数据代码。
- Flutter OTA、BLE transport、状态模型或 UI 代码。
- Cloudflare Worker、API、D1 schema 或 migration。
- 发布、签名、上传、注册或下载工具。
- OTA 产品合同、任务看板或验收治理文件。

这些修改即使不在本轮写入白名单中，也可能污染“现有入口”和接口调查。

发现语义相关的未提交修改时：

- 停止所有编辑。
- 列出相关文件及可能影响的任务。
- 不得把未提交实现当作已接受的规范依据。
- 不得自行改用 HEAD、其他分支或历史提交作为替代基线。

只有确认与 OTA 审计无关的修改才能避开继续，并必须保持未动。

禁止执行：

- git stash
- git clean
- 回退、恢复或覆盖用户修改
- 移动或删除无关未跟踪文件

## 3. 冻结状态预检

编辑任何既有规范文件前，必须先确认其治理状态。

判断依据包括：

- PLAN-OTA-EXEC.md readiness 矩阵。
- 文件自身的版本或治理标记。
- 对应版本化合同。
- 仓库现有治理规则。

规则：

- FROZEN 文件不得原位修改。
- 治理状态无法确定时，不得默认可修改。
- 已冻结文件需要变更时，只登记修订建议、影响范围和建议目标版本。
- 未经用户授权，不得自行创建冻结文件的后继版本。
- 若冻结文件阻塞共享合同设计，应停止受影响任务，不得绕过合同。
- DRAFT_PENDING_REVIEW 文件可以在白名单内原位补充。
- REVIEWED 文件是否可编辑必须按仓库规则判断；无法确认时停止该项工作。

## 4. 严格写入白名单

本轮只允许修改或创建：

- docs/ota-cross-system-contracts.md
- docs/ota-spec-decisions.md
- docs/ota-prompts/**
- PLAN-OTA-EXEC.md
- Tools/provenance/manifest_profiles.json
- .github/workflows/acceptance-governance.yml
- tests/ota/test_acceptance_bundle.py

白名单是封闭集合。

如果发现更合适的既有规范文件但它不在白名单内：

- 只报告文件路径和建议修改内容。
- 停止该项编辑。
- 不得以“更精确”或“避免重复”为理由扩大白名单。

禁止修改：

- 生产源码。
- 构建脚本。
- Flutter、Worker 或 MCU 实现。
- D1 migration。
- P2-6 及更早任务的已收口提示词。
- 用户无关文件。
- 白名单外的规范文件。

以下冻结文档只读：

- PLAN-OTA.md
- docs/ota-binary-contracts.md
- docs/acceptance-execution-contract.md

不得执行 commit、push 或 merge。

## 5. 按领域确定权威来源

不得使用简单的全局文件优先级。按领域确定权威来源：

- PLAN-OTA.md：产品目标、阶段范围和产品门槛。
- docs/ota-binary-contracts.md：BLE 二进制协议唯一真相源。
- PLAN-OTA-EXEC.md：任务 ID、顺序、范围、显式依赖和任务级 readiness 状态唯一来源。
- docs/ota-cross-system-contracts.md：P2-6 后 Flutter、HTTP、D1、发布链等跨系统规则的冻结候选来源。
- docs/ota-prompts/**：派单说明，只能引用并落实合同，不得覆盖合同。
- 现有源码：仅用于确认已有组件、调用入口和实现缺口，不得反向取代冻结合同。
- 示例、历史记录和注释：默认属于非规范性内容，除非权威合同明确声明其具有规范性。

docs/ota-cross-system-contracts.md 在本轮只能是冻结候选，不得由本轮 Spec agent 宣布为已冻结。

## 6. 任务范围和看板权限

以 PLAN-OTA-EXEC.md 中的实际文档顺序和显式依赖盘点 P2-6 之后的全部任务。

不得：

- 按任务编号进行字符串或数字排序。
- 直接假定只有 P3、P4、P5。
- 漏掉 P2-6 后可能存在的其他 P2 卡。
- 新增或删除任务。
- 重排任务顺序。
- 修改任务 ID、任务范围或显式依赖。
- 合并或拆分现有任务。
- 为同一卡创建第二份提示词。

如果任务顺序、范围或依赖与其他权威材料冲突：

- 保持看板现状不变。
- 登记 NEEDS_DECISION。
- 记录冲突双方、影响任务和推荐处理方式。
- 不得直接修改看板结构。

如果 readiness 矩阵尚不存在，可以新增矩阵结构，但只能镜像现有任务。

将每张卡分类为：

- IMPLEMENTATION
- EXPERIMENT
- INTEGRATION
- ACCEPTANCE

已有未冻结提示词应原位审计和补充；已有冻结提示词不得修改。

## 7. 状态唯一来源

任务级四项状态组合的唯一来源是 PLAN-OTA-EXEC.md 中的 readiness 矩阵。

任务级状态字段为：

- content_readiness
- governance_maturity
- dependency_state
- dispatch_eligibility

这些任务级字段不得在提示词、接口合同或决策日志中重复维护。

readiness 矩阵还应维护以下非状态路由字段：

- prompt_path
- spec_block_reason

P2-6 后每张任务行必须满足且只能满足其中一种情况：

- prompt_path 指向唯一一个实际存在的任务提示词，spec_block_reason 为空。
- 因冻结、白名单、基线冲突或其他明确原因无法创建提示词时，prompt_path 为空，spec_block_reason 记录可验证的阻断原因。

不得同时填写 prompt_path 和 spec_block_reason，也不得两者同时为空。

所有非空 prompt_path 在 P2-6 后 readiness 行中必须全局唯一，同一个提示词文件不得被两张任务卡共同引用。

prompt_path 必须使用仓库相对 POSIX 路径，例如 docs/ota-prompts/prompt-P3-1-implementation.md，并满足：

- 不得使用绝对路径。
- 不得以 ./ 开头。
- 不得包含反斜杠、.. 路径段或重复分隔符。
- 规范化并解析真实目标后仍必须位于仓库的 docs/ota-prompts/ 目录内。
- 唯一性必须按规范化后的仓库相对路径比较，不能只比较原始字符串。

每个 prompt_path 指向的任务提示词必须恰好包含一行机器可读任务标识，格式为：

task_id: <任务 ID>

该行必须完整匹配正则 ^task_id: (?P<id>\S+)$，不得带项目符号、引号、前后附加文字或行尾注释。

该 task_id 必须与引用它的 readiness 行任务 ID 完全一致。task_id 是稳定身份标识，不是任务状态，因此不违反任务状态只由 readiness 矩阵维护的规则。

除检查 readiness 已引用文件外，还必须反向枚举 docs/ota-prompts/ 中的非模板 Markdown 提示词。对于 task_id 属于 P2-6 后看板任务的文件：

- 每个任务 ID 最多只能对应一个文件。
- 该文件必须由同一任务的 readiness 行通过 prompt_path 唯一引用。
- 文件名中声明的任务 ID、文件内 task_id 和 readiness 行任务 ID 必须一致。
- 出现第二份同 task_id 文件时，即使未被看板引用，也必须判定治理测试失败。

对于文件名表明属于 P2-6 后任务、但缺少 task_id 或 task_id 格式错误的非模板提示词，也必须判定失败，禁止通过删除 task_id 绕过反向枚举。

正向和反向检查均排除模板、P2-6 及更早历史提示词和本地元提示词。

逐卡提示词只记录：

- 对应任务 ID。
- readiness 矩阵引用。
- 权威合同条款引用。
- 稳定的实现边界。

提示词不得复制任务状态值。

跨系统合同可以维护接口级字段：

- interface_completeness
- clause_maturity
- blocking_decisions
- affected_tasks

interface_completeness 允许值：

- COMPLETE
- INCOMPLETE
- BLOCKED_BY_DECISION

interface_completeness 按以下优先顺序聚合：

1. 存在阻断性 OPEN/PROPOSED 决策时，为 BLOCKED_BY_DECISION。
2. 否则，任一必需规范字段、语义、错误规则或测试点尚未定义时，为 INCOMPLETE。
3. 否则，为 COMPLETE。

clause_maturity 允许值：

- DRAFT_PENDING_REVIEW
- REVIEWED
- FROZEN

条款成熟度顺序为 DRAFT_PENDING_REVIEW < REVIEWED < FROZEN。接口行引用多个规范条款时，clause_maturity 取最低成熟度。本轮新建或修改的接口条款只能为 DRAFT_PENDING_REVIEW。

blocking_decisions 只能引用实际存在的决策 ID；affected_tasks 只能引用 PLAN-OTA-EXEC.md 中实际存在的任务 ID。

接口级状态和任务级状态不是同一对象。跨系统合同不得记录任务级 dispatch_eligibility。

静态检查必须区分：

- 任务级状态组合只能出现在 PLAN-OTA-EXEC.md readiness 矩阵。
- 接口级完整度和条款成熟度可以出现在跨系统合同中。

## 8. 任务状态模型和聚合规则

### 8.1 内容完整度

允许值：

- READY
- NEEDS_DECISION
- DEFERRED_ACCEPTANCE

按以下优先顺序聚合：

1. 存在阻断性产品、协议、安全、性能、资源或跨领域合同决策时，任务为 NEEDS_DECISION。
2. 否则，存在某项规范性验收定义必须依赖尚未产生的实现产物才能确定时，任务为 DEFERRED_ACCEPTANCE。
3. 否则，任务为 READY。

产品、安全、性能和资源门槛缺失时必须使用 NEEDS_DECISION，不得等待实现结果后反向拟合。

DEFERRED_ACCEPTANCE 仅适用于规范性验收定义本身当前无法确定，例如：

- 实现完成后才能确定的生成符号或入口。
- 由最终构建结构决定且当前无法规范化描述的精确 manifest 条目。
- 只有产物生成后才能确定的证据绑定结构。

以下情况不构成 DEFERRED_ACCEPTANCE：

- 尚未执行测试。
- 尚未得到真实观测值。
- 尚未生成证据文件。
- 尚未运行 CI。
- 尚未构建固件。
- 尚未执行真机验收。

如果采集方法、字段、证据类型和判定规则已经明确，即使尚未执行，也可以标记 READY。

以下内容不得延期：

- 产品门槛。
- 安全比例。
- 性能阈值。
- 资源上限。
- 协议语义。
- 错误处理规则。
- 实现责任边界。

### 8.2 治理成熟度

允许值：

- DRAFT_PENDING_REVIEW
- REVIEWED
- FROZEN

成熟度顺序为：

DRAFT_PENDING_REVIEW < REVIEWED < FROZEN

任务治理成熟度取以下全部必需规范中的最低成熟度：

- 任务提示词。
- 任务引用的共享合同条款。
- 任务引用的其他必需规范。
- 任务必须依赖的验收定义。

只有全部必需规范均为 FROZEN，任务治理成熟度才能为 FROZEN。

本轮新增或修改的规范只能是 DRAFT_PENDING_REVIEW。

### 8.3 依赖状态

允许值：

- SATISFIED
- BLOCKED_BY_DEPENDENCY
- NOT_APPLICABLE

聚合规则：

1. 任一阻断依赖未完成时，为 BLOCKED_BY_DEPENDENCY。
2. 任务没有前置依赖时，为 NOT_APPLICABLE。
3. 任务存在依赖且全部完成时，为 SATISFIED。

必须列出具体阻断任务或外部依赖。

验收范围已经完整、只是前置实现未完成时，应使用 READY + BLOCKED_BY_DEPENDENCY，不得误记为 DEFERRED_ACCEPTANCE。

### 8.4 派单资格

允许值：

- NOT_DISPATCHABLE
- DISPATCHABLE

派单资格是派生结果：

DISPATCHABLE = content_readiness 为 READY + governance_maturity 为 FROZEN + dependency_state 为 SATISFIED 或 NOT_APPLICABLE + 无阻断性 OPEN/PROPOSED 决策 + 必需治理检查通过

任何一个条件不满足时均为 NOT_DISPATCHABLE。

任何引用本轮新增或修改规范的任务，本轮结束时必须保持 NOT_DISPATCHABLE。

## 9. 冲突分类

不得把普通文档错误全部转化为开放决策。

### 9.1 提示词与权威合同不一致

- 提示词未冻结时，直接修正提示词。
- 提示词已冻结时，登记修订建议。
- 不创建产品决策。

### 9.2 源码未实现冻结合同

- 记录为实现缺口或任务阻塞。
- 不得反向修改合同迁就源码。

### 9.3 两个权威合同发生重叠冲突

- 登记 NEEDS_DECISION。
- 记录冲突条款和受阻任务。

### 9.4 权威归属不清或缺少产品规则

- 登记 NEEDS_DECISION。

### 9.5 示例、名称、链接或非规范性文字过期

- 在白名单和治理状态允许时直接修正。
- 不升级为产品决策。

### 9.6 冻结合同疑似错误

- 不得修改冻结合同。
- 登记精确冲突、影响和建议裁定路径。

规范文档必须区分规范性条款和非规范性示例。非规范性示例不得成为新增产品规则。

## 10. 决策登记

创建或补充 docs/ota-spec-decisions.md。

该文件只是决策过程记录和追踪索引，不是接口真相源。

每项至少包含：

- decision_id
- 问题描述
- 所属领域
- 候选方案
- 推荐方案及理由
- 状态：OPEN / PROPOSED / DECIDED / SUPERSEDED
- 决策责任人
- 受阻任务
- 最终落盘的目标领域合同及条款 ID
- 已有裁定依据

决策 ID 使用 OTA-DEC-NNN 格式，并满足：

- 全文件唯一。
- 按现有最大编号单调递增。
- 不得重新编号。
- 不得复用已删除或 SUPERSEDED 的编号。
- 不得因文档重排改变编号。

规则：

- 本轮可以新增 OPEN 或 PROPOSED。
- 没有用户裁定或既有权威依据时不得标记 DECIDED。
- OPEN 或 PROPOSED 不得被提示词当作冻结要求。
- 决策完成后必须把结果写入对应领域合同。
- 任务提示词最终引用领域合同，不长期引用决策日志作为接口依据。
- 被替代的决定标记 SUPERSEDED，不得删除历史记录。

## 11. 稳定规范条款 ID

共享跨系统合同中所有会被任务提示词引用的规范性规则都必须分配稳定条款 ID。

条款 ID 不仅覆盖具体接口，还必须覆盖：

- 全局错误封装。
- 超时和重试。
- 取消和恢复。
- 幂等。
- 版本兼容。
- 安全和鉴权。
- 摘要和签名。
- 未知字段处理。
- 资源或协议边界。
- 跨系统字段映射。

示例：

- OTA-XC-INFO-MAPPING
- OTA-XC-HTTP-LATEST
- OTA-XC-HTTP-ERROR
- OTA-XC-RETRY-POLICY
- OTA-XC-COMPATIBILITY
- OTA-XC-SECURITY
- OTA-XC-D1-RELEASE
- OTA-XC-FLUTTER-TRANSPORT

条款 ID 必须：

- 全文唯一。
- 语义稳定。
- 不因标题润色或章节移动而改变。
- 已冻结后不得复用给不同语义。
- 被替代时保留旧 ID 并标记替代关系。

任务提示词引用条款 ID，不依赖 Markdown 标题或行号。

## 12. 跨系统合同

优先审计白名单中的既有文件。若不存在且目标未被冻结，创建 docs/ota-cross-system-contracts.md。

至少包含：

- 规范性范围和非目标。
- 稳定规范条款 ID。
- 接口矩阵。
- Flutter DTO。
- MCU INFO 到 Flutter DTO 的字段映射。
- Flutter DTO 到云端请求的字段映射。
- 元数据 API 的请求、成功 JSON 和失败 JSON。
- 二进制上传、下载接口的媒体类型、长度、摘要头、成功状态和失败 JSON。
- D1 数据模型、唯一键、migration/backfill 要求和状态迁移。
- 发布 CLI 的输入、输出、退出码和资产命名。
- 发布资产到注册元数据的映射。
- BLE transport 生命周期和责任所有者。
- 全局错误封装。
- 超时、重试、取消、恢复和幂等语义。
- 版本兼容和未知字段处理。
- 鉴权、摘要、签名和输入校验边界。
- 规范性测试向量。
- 非规范性示例。

不得复制 docs/ota-binary-contracts.md 中的 BLE 字节协议，只能引用其权威章节。

同一字段在 MCU、Dart、JSON、SQL 和 CLI 中名称不同时，必须给出明确映射表。

接口矩阵至少记录：

- Producer
- Consumer
- 传输介质
- 条款 ID
- schema 或结构引用
- 生命周期所有者
- 错误语义
- 幂等规则
- 兼容规则
- interface_completeness
- clause_maturity
- blocking_decisions
- affected_tasks

接口矩阵不得保存任务级 readiness 或派单资格。

## 13. 逐卡派单 Spec

在 docs/ota-prompts/ 下，为每张后续任务卡创建或补充对应提示词。

P2-6 后新提示词沿用仓库现有命名规则：

prompt-Px-y-<type>.md

文件名中的任务 ID 必须与文件内 task_id 及 readiness 行任务 ID 完全一致。

每张提示词必须包含：

- 恰好一行位于文件前部、完整匹配 ^task_id: (?P<id>\S+)$ 的机器可读任务标识，且与文件名及 readiness 行一致。
- 任务类型。
- PLAN-OTA-EXEC.md readiness 行引用。
- 目标与非目标。
- 前置依赖引用。
- 权威合同稳定条款 ID。
- 现有组件和代码入口。
- 输入输出及调用方向。
- 状态机和生命周期所有者。
- 错误、超时、重试、取消、恢复和幂等规则。
- 允许修改的文件或目录。
- 禁止修改的合同、组件和生产红线。
- 必须新增或调整的测试。
- 完成判据。
- 停止条件。
- 仍需实现或验收会话采集的证据。
- Luna 可以自行决定的内部实现细节。
- 阻断性决策 ID。

禁止：

- 在提示词中重新声明规范性 byte、JSON、SQL 或 DDL schema。
- 复制共享合同字段表。
- 把实现偏好写成产品合同。
- 把 OPEN/PROPOSED 决策写成强制要求。
- 重复维护任务级状态。
- 为同一卡创建多份竞争提示词。

## 14. P5 验收任务

按 PLAN-OTA-EXEC.md 中实际存在的每张 P5 卡分别创建验收 Spec。

每张验收 Spec 只定义：

- 验收范围。
- 前置依赖。
- Production、Validation、Governance 分类。
- 证据采集方法。
- 证据字段和证据类型。
- 判定规则。
- 结果分类。
- 失效条件。
- 必须依赖未来实现产物才能确定的规范性验收定义。
- 创建正式版本化 acceptance contract 的前置条件。

不得在本轮创建或冻结 docs/acceptance-contracts/Px-y-v1.contract.json。

测试尚未执行、尚无观测值或尚无证据文件，不影响验收 Spec 标记为 READY，只要采集和判定规则已经完整。

## 15. 看板更新权限

对 PLAN-OTA-EXEC.md 的修改仅限：

- 补充或更新提示词路径。
- 补充或更新共享合同条款引用。
- 新增或更新 readiness 矩阵中的状态。
- 在看板已经存在的专用 Spec 或会话记录区追加必要记录。

必须保持不变：

- 任务 ID。
- 任务顺序。
- 任务范围。
- 显式依赖。
- 既有产品定义。
- 已冻结结论。

如果看板不存在专用 Spec 或会话记录区，不得新建泛化日志区，只在最终报告中记录本轮过程。

若发现任务结构问题，只登记决策，不得直接修改。

readiness 矩阵是任务四项状态唯一来源，不得创建第二份任务状态文件。

PLAN-OTA-EXEC.md 可能包含混合 EOL：

- 禁止整文件格式化。
- 禁止统一换行。
- 必须使用字节安全或精确逐行修改。
- 修改后验证非目标行及原有 EOL 未变化。

## 16. Governance 接线

确认新增规范文件被 Governance manifest 和 Acceptance Governance workflow 覆盖。

若现有规则已完整覆盖，不得进行无意义修改。

静态测试必须保持轻量，只验证可机械判断的规则，例如：

- 规范性提示词未落入 .claude/。
- 新增合同和提示词被 manifest 与 CI paths 覆盖。
- 提示词引用的文件和稳定条款 ID 存在。
- 每张提示词包含必需章节。
- 提示词未出现规范性 DDL、字节偏移表或 JSON Schema 声明。
- OPEN/PROPOSED 决策未被标成冻结要求。
- decision_id 唯一且未复用。
- 稳定条款 ID 唯一。
- 提示词和合同中引用的每个 OTA-DEC-NNN 都存在于 docs/ota-spec-decisions.md。
- 决策登记中的每个受阻任务 ID 都存在于 PLAN-OTA-EXEC.md。
- P2-6 后每张 readiness 行都恰好具有一个有效 prompt_path，或一个非空 spec_block_reason，且二者不得同时存在。
- 所有非空 prompt_path 都是规范化的仓库相对 POSIX 路径，解析后位于 docs/ota-prompts/，且按规范化结果全局唯一。
- 每个 prompt_path 指向的文件都恰好包含一个完整匹配 ^task_id: (?P<id>\S+)$ 的任务标识，且与文件名及 readiness 行任务 ID 完全一致。
- 反向枚举 docs/ota-prompts/ 中的非模板提示词；属于 P2-6 后任务的每个 task_id 最多对应一个文件，且该文件必须由同任务 readiness 行唯一引用。
- 文件名属于 P2-6 后任务但缺少合法 task_id 的非模板提示词会导致测试失败。
- 正向和反向检查均排除模板、P2-6 及更早历史提示词和本地元提示词。
- 任务级四项状态字段只出现在 PLAN-OTA-EXEC.md readiness 矩阵。
- 合法的接口级 interface_completeness 和 clause_maturity 不被误报。

不得：

- 构建通用 Markdown 解析框架。
- 承诺语义级文档一致性分析。
- 通过复制 schema 实现一致性检查。

## 17. 控制 Spec 成本

1. 禁止先实现生产代码、最小功能或完整 harness，再反推 Spec。
2. 禁止修改产品源码验证普通设计选择。
3. 禁止运行真机、完整 GCC、AC5 或模拟器验收。
4. 禁止为选择普通内部组件开展无边界技术研究。
5. 高风险协议或链接可行性问题可以登记未来最小探针要求，本轮默认不执行探针。
6. 无法通过现有合同确定的问题应登记决策，不得自行发明产品规则。
7. 不得从历史观测值反向拟合门槛。
8. 相同规则只在共享合同定义一次。
9. 每张提示词只写到足以派单和验收的最小深度。
10. 不复制 P2-6 的重型预实现过程。

## 18. 测试和写入副作用控制

本轮禁止：

- 安装新依赖。
- 访问网络。
- 下载工具或数据。
- 使用系统临时目录保存可控输出。
- 在项目外生成可控缓存、日志或测试产物。

运行测试前必须：

- 将可控 TEMP、TMP、Python cache、pytest basetemp 和工具缓存指向项目内既有忽略目录。
- 检查输出目录及父链均位于项目根目录内。
- 确认不存在 symlink、junction 或 reparse point 越界。

只运行仓库已有、本机依赖已满足的治理和静态测试。若测试需要安装依赖或联网，应跳过并报告，不得自行安装。

至少验证：

- 相关 Governance 单元测试。
- Markdown、JSON 和 YAML 本地静态检查。
- 稳定条款 ID 唯一性和引用存在性。
- 决策 ID 唯一性、单调性和未复用。
- manifest 与 workflow paths 覆盖。
- git diff --check。
- PLAN-OTA-EXEC.md 非目标行和 EOL 未污染。
- 冻结文件零差异。
- 生产源码零差异。
- 实际变更路径全部位于写入白名单。
- 新增未跟踪文件全部位于写入白名单。
- 项目内测试缓存和临时文件无非预期残留。
- 没有遗留测试进程。

不能只依赖 git status。应分别检查：

- 已跟踪差异路径。
- 未跟踪文件。
- 忽略目录中的本轮可控输出。
- 冻结文件差异。
- 生产源码差异。
- 写入白名单外差异。
- 本轮主动选择或可控的项目外写入。

最终只能声明：

“未发现本轮主动选择或可控的未经授权项目外写入。”

不得对 Codex 宿主或其他不可控运行状态作绝对承诺。

## 19. Luna-ready 判据

任务内容只有同时满足以下条件才能在看板标记为 READY：

- 精确知道要扩展的组件和接入入口。
- 所有跨系统输入输出都有唯一合同条款。
- 字段能够跨 MCU、Flutter、HTTP、D1 和发布工具逐项映射。
- 状态机和生命周期所有者明确。
- 错误、超时、重试、取消、恢复和幂等行为明确。
- 不要求 Luna 自行创造产品规则或跨层协议。
- 允许修改范围、红线和停止条件明确。
- 测试采集方法、证据字段和判定规则可执行。
- 不存在未登记的高风险歧义。

内容完整但依赖未完成时：

READY + BLOCKED_BY_DEPENDENCY + NOT_DISPATCHABLE

缺少阻断性产品决策时：

NEEDS_DECISION + NOT_DISPATCHABLE

规范性验收定义确实必须等待实现产物时：

DEFERRED_ACCEPTANCE + NOT_DISPATCHABLE

测试尚未执行或尚无真实观测值，不妨碍内容标记为 READY。

## 20. 最终报告

最终报告必须包含：

1. P2-6 后全部任务的实际清单、原有文档顺序和类型。
2. 每张任务卡在 PLAN-OTA-EXEC.md readiness 矩阵中的四项状态。
3. 各任务状态的聚合依据。
4. 既有已冻结合同。
5. 本轮建议提交人工复核的冻结候选。
6. 所有 OPEN/PROPOSED 决策及受阻任务。
7. 因既有文件已冻结而未能修改的项目。
8. 因语义相关脏基线而停止的项目。
9. 新增和修改文件清单。
10. 写入白名单检查结果。
11. 冻结文件和生产源码零差异检查结果。
12. 测试命令、退出码、通过数、失败数和跳过数。
13. 未执行的测试、构建或验收及原因。
14. 用户原有修改和未跟踪文件是否保持未动。
15. 项目内临时产物检查结果。
16. “未发现本轮主动选择或可控的未经授权项目外写入”的审计结论。
17. 明确说明未执行 commit、push、merge。
18. 明确说明本轮新增或修改的规范均为 DRAFT_PENDING_REVIEW。
19. 明确说明引用本轮新增或修改规范的任务均为 NOT_DISPATCHABLE。
20. 列出内容上已达到 Luna-ready 的任务，以及仍需裁定或等待依赖的任务。

本轮交付是供独立审查方复核的完整 Spec 候选集，不是由 Spec 作者自行批准的正式派单包。
