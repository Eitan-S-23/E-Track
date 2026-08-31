# P2-6 后续 OTA Spec 独立冻结复核指令

prompt_kind: local_meta_instruction
normative: false
review_mode: read_only

## 任务定位

你是本轮独立冻结复核方，不是 Spec 作者、落盘执行方或整改执行方。

项目根目录固定为：

    D:\github\my\E-Track

本轮目标是审查当前工作树中的 P2-6 后续 OTA Spec 候选集，判断其是否具备提交人工冻结审批的条件。

你只能审查实际文件、运行允许的轻量验证并给出结论。不得修改候选稿、代替用户裁定、宣布冻结或开始产品实现。

本文件是 .claude 下的本地元提示词，不是任务派单 Spec，不属于 docs/ota-prompts/ 的规范性提示词集合。反向枚举任务提示词时必须排除本文件。

## 1. 严格禁止

本轮不得：

- 修改、创建、删除、移动、重命名或格式化任何受审查文件。
- 使用 apply_patch 或其他方式修复发现的问题。
- 将决定从 PROPOSED 改为 DECIDED。
- 将规范从 DRAFT_PENDING_REVIEW 改为 REVIEWED 或 FROZEN。
- 将任何任务改为 DISPATCHABLE。
- 修改生产源码、D1 migration、发布实现、workflow 或正式 acceptance contract。
- 执行 commit、push、merge、stash、clean、checkout、reset、restore、rebase 或 fetch。
- 安装依赖、访问网络、部署 Worker、执行 D1 写操作或下载工具。
- 运行 GCC、AC5、Flutter build、模拟器、真机、完整实验或正式验收。
- 执行当前工作树中的未跟踪脚本或未知工具文件。
- 在 finding 后顺手修复。所有问题只能报告给 Spec 落盘 agent。

允许的唯一写入副作用是运行既有轻量测试所必需的项目内忽略缓存目录。必须先完成第 3 节的写入预检，并在结束时只清理本轮自己创建的目录。

## 2. 开始前只读检查

开始审查前必须：

1. 阅读根目录 AGENTS.md。
2. 使用用户指定的绝对路径确认唯一活动项目根目录。
3. 记录当前分支、HEAD 和本地 origin/main 引用。不得联网 fetch。
4. 记录 git status --short --untracked-files=all。
5. 枚举全部已跟踪差异、未跟踪文件和相关忽略目录。
6. 阅读完整 git diff，不得仅依赖落盘 agent 的总结。
7. 区分 OTA Spec 候选修改、用户原有未跟踪文件以及任何语义相关生产修改。
8. 检查目标目录及测试临时目录父链是否存在 symlink、junction 或其他 reparse point。
9. 不得改用其他分支、历史提交或 HEAD 文件替代当前工作树进行审查。

当前已知需要保护且不得执行、修改、移动或删除的既有未跟踪文件为：

- .cache-cmake-time-test.cmake
- .claude/cc_recover_s4.js
- .claude/ccprobe_hash.js
- .claude/ccprobe_plan.js

开始和结束时分别记录它们的存在性、大小和 SHA-256。若实际列表不同，应如实报告，不得自行恢复、删除或覆盖。

如果存在 MCU、Boot、BLE、Flutter、Worker、API、D1、Admin、发布工具或生产 workflow 的语义性未提交实现修改，且无法客观证明它们与当前 Spec 审查基线无关，停止进一步结论并返回 BLOCKED。

## 3. 测试写入预检

运行任何可能写缓存的测试前：

1. 在项目根目录内选择本轮专用的忽略目录，例如：

       .cache/post-p2-6-independent-freeze-review

2. 将目标规范化为绝对路径，确认位于项目根目录内。
3. 检查目标及其已有父目录不是 symlink、junction、mount point 或 reparse point。
4. 如果目录已经存在且无法证明属于本轮，不得复用或清理；改用另一个项目内唯一目录。
5. 将 TEMP、TMP、Python cache、pytest basetemp 和可控工具缓存全部指向该目录。
6. 使用 python -B 或 PYTHONDONTWRITEBYTECODE，避免在源码目录产生 pyc。
7. 禁止使用系统 TEMP、用户目录或项目外路径。
8. 结束时只删除本轮创建的缓存目录，并验证无测试进程残留。

如果任一工具无法覆盖项目外默认写入，跳过该工具并报告原因，不得先运行再审计。

## 4. 主要审查范围

重点审查：

- PLAN-OTA-EXEC.md
- docs/ota-cross-system-contracts.md
- docs/ota-spec-decisions.md
- docs/ota-prompts/prompt-P3-1-implementation.md
- docs/ota-prompts/prompt-P3-2-implementation.md
- docs/ota-prompts/prompt-P3-3-implementation.md
- docs/ota-prompts/prompt-P3-4-experiment.md
- docs/ota-prompts/prompt-P3-5-integration.md
- docs/ota-prompts/prompt-P4-1-implementation.md
- docs/ota-prompts/prompt-P4-2-implementation.md
- docs/ota-prompts/prompt-P4-3-implementation.md
- docs/ota-prompts/prompt-P4-4-integration.md
- docs/ota-prompts/prompt-P5-1-acceptance.md
- docs/ota-prompts/prompt-P5-2-acceptance.md
- docs/ota-prompts/prompt-P5-3-acceptance.md

同时检查工作树中已有的 Governance manifest、workflow 和测试差异，确认它们是否正确覆盖候选规范，包括：

- Tools/provenance/manifest_profiles.json
- .github/workflows/acceptance-governance.yml
- tests/ota/test_acceptance_bundle.py

以下冻结来源必须保持零差异：

- PLAN-OTA.md
- docs/ota-binary-contracts.md
- docs/acceptance-execution-contract.md
- 已冻结的 P2-6 提示词

生产源码、构建脚本、D1 migration 和正式 acceptance contract 必须保持零差异或不存在新增。

## 5. 用户裁定基准

以下内容是本次审查使用的用户裁定基准。逐项核对决定登记、共享合同、接口矩阵、readiness 和受影响提示词，不得把候选稿自身当作唯一证明。

### OTA-DEC-001

用户选择 B。

BLE wire model 固定为精确 8 字节：

    E-Track\0
    hex = 45 2D 54 72 61 63 6B 00

映射到云端正式 deviceModel：

    e-track-at32f435

必须区分大小写，不允许别名、前缀、模糊匹配或默认回退。model 映射与 hw_rev/layout_id 兼容性检查是独立阶段。错误语义必须区分 UNKNOWN_DEVICE_MODEL 与硬件或布局不兼容。

### OTA-DEC-002

用户选择 A。

跨系统镜像身份是 finalized app.bin 在 [0:image_len] 上的原始 SHA-256。

必须区分三个摘要域：

1. raw image identity：
   BLE INFO.image_sha256、Flutter currentImageSha、D1 target/base identity、.etu base_sha8。
2. header-integrity digest：
   fw_header.image_sha256、Boot 校验、ETSL.sha8、包或 patch 结果中的 header digest、candidateImageSha8。
3. asset integrity：
   .etu、recovery 和验收证据文件本身的完整文件摘要。

完整合法 INFO 是 latest 查询前置条件。合法 raw identity 未命中可用 patch 时可以退回已验证 full。历史目标 release 缺少权威 raw identity 时必须 legacy 隔离，不得进入 latest。不得把同名的 INFO 字段和 fw_header 字段解释为同一算法。

### OTA-DEC-003

用户选择 B。

P3-4 只能按照已冻结门槛测量并选择满足全部门槛的最高支持 baud，不能修改门槛。

固定参数：

- referencePackageBytes=1048576
- p95MaxSeconds=120
- singleRunMaxSeconds=150
- minEffectiveThroughputKiBps=9
- maxDataRetransmissionRatePercent=1
- consecutiveSuccessfulRuns=30
- soakDurationHours=4
- allowedUnrecoverableErrors=0
- reconnectSuccesses=10/10
- ackTimeout=clamp(3×P99_ACK,500ms,2000ms)
- maxRetries=5
- noDurableProgressAbortSeconds=30

吞吐公式：

    effectiveThroughputKiBps = referencePackageBytes / 1024 / elapsedSeconds

elapsedSeconds 使用单调时钟，从 BEGIN 发送开始到成功 END ACK 到达。

P99 使用 nearest-rank ceil(0.99×N)。每个唯一 DATA 段只形成一个样本，从首次完整发送结束到第一个明确证明该段已被接收的有效 ACK。重传不创建新样本。不同 baud、timeout 或 retry 参数组合的结果不得拼接。

### OTA-DEC-004

用户选择 A。

latest 强制要求 appVersionCode，范围为 0..2100000000。

- 缺失、非整数、负数或超出范围：400 INVALID_PARAMETER。
- 只有确认确实存在更新后，才检查最低 App 版本。
- 低于 minAppVersionCode：426 CLIENT_TOO_OLD。
- 426 响应可以包含 minAppVersionCode，但不得包含 asset、下载 URL、token 或签名信息。
- 不得把 CLIENT_TOO_OLD 转换为 NO_UPDATE。
- download 不重复检查 App 版本。
- Flutter 收到 426 后必须在下载和 BLE 前终止。

### OTA-DEC-005

用户选择 B。

只支持单区间 bytes=N-：

- partialRetentionHours=24。
- 网络失败和 App restart 保留 .part。
- 用户明确取消删除 .part。
- sidecar 必须原子写入。
- 身份绑定 assetId、releaseId、sha256、sizeBytes 和 ETag。
- 使用 If-Range。
- 匹配返回 206。
- validator 不匹配或服务器返回 200 时截断并从零下载。
- offset 大于等于 size 时处理 416，删除旧 partial 并重新 latest。
- multi-range 和 suffix-range 返回 400 INVALID_PARAMETER。
- URL 过期后重新 latest；只有 metadata 身份完全一致才能继续。
- 最终必须重新验证整文件长度和 metadata SHA-256 后才能进入 BLE。
- 每个 asset 最多一个 partial。
- Content-Digest 的响应体覆盖范围不得与完整资产 SHA 混淆。

### OTA-DEC-006

用户选择 A。

正式名称：

    e-track-at32f435-v{targetVersion}-full.etu
    e-track-at32f435-v{baseVersion}-to-v{targetVersion}-patch.etu
    recovery-vX.Y.Z.bin

正式版本格式：

    ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)$

不允许 prerelease/nightly 后缀和前导零。deviceModel 与 role 使用小写。最大 128 ASCII bytes。非法或重复名称必须在任何远端写入前失败。

### OTA-DEC-007

用户选择 B。

范围键为 appId+deviceModel。

- recentFormalReleaseCount=10。
- minimumRetentionDays=365。
- 只有同时超出 N 和 T 才能进入候选清理。
- 最近 release 按 version_code DESC。
- 年龄使用不可变 created_at。
- ready patch 基版、stable/beta channel 指针及未完成注册、恢复或清理任务必须引用保护。
- recovery 不允许自动删除。
- 清理器只能生成候选 manifest。
- 进入 archived 隔离前需要产品或运营 owner 与 Cloudflare 成本责任人双人批准。
- archiveQuarantineDays=30。
- 隔离期结束后再次 fail-closed 检查并再次满足审批要求，才能删除 R2。
- GitHub Release 默认不得删除，另行双人批准。
- 禁止 wildcard 或覆盖旧 key。
- D1 身份和审计记录保留，删除后 asset 状态为 r2_deleted。
- 每月执行一次候选清理。

### OTA-DEC-008

用户选择 A。

使用隔离 rehearsal 和 production 两阶段流程：

- rehearsal environment 为 firmware-rehearsal。
- 使用独立 staging Worker、D1 和 R2 bucket。
- staging R2 bucket 为 trace-update-staging-releases。
- rehearsal 不允许任何 production 副作用，也不创建 GitHub prerelease。
- 必须验证三资产 SHA/size、patch 逐字节自验、recovery 校验、metadata SHA、staging R2 全字节 readback、register ready/idempotency 和生产资源零副作用。
- 独立 OTA 架构 reviewer 审批 rehearsal。
- repository owner 人工且可审计地设置 OTA_BOOT_CHAIN_READY。
- 首次 production publish 必须在任何生产副作用前匹配已批准 rehearsal 的 commit、版本输入、canonical metadata 和资产摘要。
- production 仍需 firmware-production environment 独立审批。
- governed OTA/release-chain 发生语义回归时必须重新置 false 并重新 rehearsal。
- workflow 不得自动修改 gate。

### OTA-DEC-009

用户选择 A。

依赖方向统一解释为“前置任务 → 被依赖任务”：

    P4-2 → P4-1
    P4-2 → P3-5

P4-2 不依赖 P4-1。P4-1 与 P3-5 不存在自动依赖。

P4-2 必须先基于 schemaVersion=2 的 versioned schema fixture 实现合同；P4-1 后续连接真实资产；P3-5 等待 P4-2。禁止临时 register stub、手改 D1 和任意静态 JSON。

### OTA-DEC-010

用户选择 A。

旧数据只能通过权威、版本化 backfill manifest 选择性回填。必须逐字节验证身份和证据。无法验证的记录保持 legacy 隔离，不得进入 latest、patch 选择或被推断补齐。migration/backfill 必须 fail closed。

### OTA-DEC-011

用户选择 A。

Admin release action 使用独立 Idempotency-Key，持久化 24 小时：

- 不能用 X-Request-Id 代替。
- 同 key、同 fingerprint 返回原结果。
- 同 key、不同 fingerprint 返回 IDEMPOTENCY_CONFLICT。
- 结果已超过持久化窗口且不能安全重放时返回 IDEMPOTENCY_RESULT_EXPIRED。
- recovery URL 的 300 秒过期不等于幂等记录过期。
- 必须覆盖并发请求、冲突、24 小时边界和 URL 过期后的行为。

### OTA-DEC-012

用户选择 A。

tokenVersion=2。

querySet：

    tokenVersion,assetId,releaseId,kind,purpose,expiresAt,keyVersion,signature

缺失、空值、重复或未知参数全部拒绝。

canonical 顺序：

    2
    大写 HTTP 方法
    assetId
    releaseId
    kind
    purpose
    expiresAt
    keyVersion

字段以 LF 分隔。expiresAt 是十进制 Unix epoch 秒。签名使用 HMAC-SHA256，Base64URL 无 padding。

- ttlSeconds=300。
- public-ota 只允许 full/patch。
- admin-recovery 只允许 recovery。
- 部署后新 signer 只签 v2。
- v1 只接受部署前签发的 public full/patch URL。
- v1 recovery 始终拒绝。
- v1 必须同时满足 now < expiresAt 和 now < v2CutoverEpoch+300。
- expiresAt 为排他截止时刻，now >= expiresAt 即 TOKEN_EXPIRED。
- v2CutoverEpoch 必须固定并审计，不能使用进程启动时间。
- 300 秒结束后立即删除或禁用 v1 verifier。

## 6. Readiness 和治理检查

重点核查：

1. PLAN-OTA-EXEC.md 是任务四项状态唯一来源。
2. content_readiness 只能使用 READY、NEEDS_DECISION、DEFERRED_ACCEPTANCE。
3. READY_FOR_REVIEW 不是合法 content_readiness 值。如果它实际出现在规范性矩阵中，至少记录为 HIGH finding；如果只是落盘 agent 的非规范性报告措辞，应明确说明没有状态模型问题。
4. governance_maturity 当前必须保持 DRAFT_PENDING_REVIEW。
5. dispatch_eligibility 当前必须保持 NOT_DISPATCHABLE。
6. dependency_status 必须反映实际前置任务，不得因为 Spec 内容完整而伪造 SATISFIED。
7. OTA-DEC-001 至 OTA-DEC-012 当前都应保持 PROPOSED，不得出现 DECIDED。
8. PROPOSED 决定仍必须保留阻断传播，不得被合同或提示词当作已经冻结的授权。
9. 提示词不得维护任务级状态值，只能引用 PLAN readiness 行。若实际复制 READY、DRAFT_PENDING_REVIEW 或 NOT_DISPATCHABLE 等规范性状态，必须报告。
10. P3-4 的生产参数尚未通过实验选出属于执行依赖，不应被写成新的产品决定缺口。
11. DEC-008 的 reviewer、owner 和 production environment 审批属于执行 gate，不应被误写为 Spec 内容不完整。
12. DEC-010 的真实 manifest 和历史数据证据属于未来实现或验收依赖，不得通过伪造 fixture 或猜测数据解除。
13. 不得因为所有内容进入复核而将十二张卡全部标为 DISPATCHABLE。

## 7. 合同和提示词检查

必须验证：

- 稳定条款 ID 唯一且引用存在。
- 所有接口字段在 MCU、Flutter、HTTP、D1 和发布工具间具有明确映射。
- JSON、SQL、CLI、Dart 和 MCU 名称不同处均有显式映射。
- BLE 字节布局只引用冻结二进制合同，没有复制或重定义。
- HTTP latest、download、register、Admin 的方法、路由、鉴权、成功响应、失败响应、状态码和信息最小化完整。
- Range、ETag、If-Range、206、416、Content-Digest 和最终整文件摘要语义没有混用。
- D1 schema、唯一键、FK/CHECK、CAS、append-only、migration、backfill、legacy、retention 和审计规则完整。
- 发布 CLI 输入、输出、退出码、正式资产名称及资产到注册 metadata 的映射完整。
- BLE lifecycle owner、超时、重试、取消、恢复、幂等和实验统计规则完整。
- token v2 canonical、exclusive expiry、v1 cutover 和 recovery 隔离具有规范性测试向量。
- Admin 幂等并发、冲突、24 小时结果保存与 300 秒 URL 过期具有测试向量。
- 清理 manifest、双人审批、30 天隔离、再次检查和 fail-closed 行为具有测试向量。
- rehearsal 与 production 快照匹配、零生产副作用和 gate 复位条件具有测试向量。
- 规范性内容和非规范性示例明确分开。
- 提示词只引用共享合同，不复制第二套 byte、JSON、SQL 或 DDL schema。
- 每张提示词恰好有一个机器可读 task_id。
- task_id、文件名、PLAN readiness 行和 prompt_path 一致。
- 所有非空 prompt_path 全局唯一。
- 对 docs/ota-prompts/ 做反向枚举，确认不存在未被看板引用的竞争提示词。
- 模板、历史提示词和 .claude 本地元提示词不得被误计入任务提示词集合。
- 每张卡的目标、非目标、入口、生命周期、错误行为、修改范围、红线、测试、完成判据、停止条件和证据要求完整。
- P5 文件只定义验收范围和未来证据要求，没有提前创建正式 versioned acceptance contract。

## 8. 必须执行的验证

不得安装依赖或联网。只运行仓库已有且本机依赖已满足的轻量检查。

至少执行：

    python -B tests/ota/test_acceptance_bundle.py

必须记录：

- 完整命令。
- 退出码。
- 总数、通过数、失败数和跳过数。
- 每个跳过原因。
- 如果无法运行，说明精确阻断原因，不能把未运行视为通过。

同时执行：

- git diff --check。
- Markdown UTF-8、围栏和尾随空白检查。
- JSON 解析。
- YAML 本地解析；缺少既有依赖时跳过并报告，不得安装。
- 稳定条款 ID 唯一性及引用存在性检查。
- decision ID 唯一性及受阻任务传播检查。
- prompt_path、task_id、文件名和反向枚举检查。
- manifest 与 workflow paths 覆盖检查。
- PLAN-OTA-EXEC.md 非目标字节和 EOL 审计。
- 冻结文件零差异检查。
- 生产源码零差异检查。
- 全部已跟踪差异路径、未跟踪路径和忽略目录审计。
- 是否存在正式 acceptance contract、migration、fixture 实现或探针新增。
- 本轮测试缓存和进程残留检查。
- 本轮主动选择的全部输出路径及项目外写入审计。

不得运行 GCC、AC5、Flutter build、Worker deploy、D1 migration、模拟器、网络、真机或正式验收。

## 9. Finding 分级

findings 必须放在报告最前面，按严重程度排序，并提供准确文件路径和行号。

### BLOCKER

- 语义相关脏生产基线。
- 冻结合同或生产源码被修改。
- 用户选择被反向解释。
- 两个摘要域或协议真相源冲突。
- 存在未经授权的实现、migration 或正式 acceptance contract。
- 无法建立可靠审查基线。

### HIGH

- 使用非法 readiness 状态。
- 依赖方向错误或形成循环。
- PROPOSED 决定被当作冻结要求，或阻断被提前解除。
- 缺少跨系统 schema、错误语义、幂等、恢复或安全边界。
- 提示词复制第二套规范。
- task_id 或 prompt_path 映射不完整，或存在竞争提示词。
- Governance 测试失败。

### MEDIUM

- 测试向量、字段传播、停止条件或证据要求不完整。
- 非规范性示例可能被误认为产品规则。
- Governance 机械检查存在可绕过缺口。

### LOW

- 不影响语义的命名、链接、可读性或非规范性文字问题。

不要把普通拼写、过期链接或实现缺口错误升级成产品决定。

## 10. Verdict

最终只能给出以下三种结论之一。

### APPROVE_FOR_FREEZE

没有 BLOCKER、HIGH 或 MEDIUM finding；全部必需测试通过，或者只有已解释且不影响结论的环境能力跳过。

该结论仅表示建议用户提交正式冻结审批，不代表你已经批准、冻结、将决定标为 DECIDED 或允许派单。

### CHANGES_REQUIRED

存在可以由 Spec 落盘 agent 修复的问题。列出最小整改清单，但不得直接修改。

### BLOCKED

基线污染、权威来源冲突、缺少必要用户裁定或无法完成可靠验证。

## 11. 最终报告格式

按以下顺序输出：

1. Findings，按严重程度排序，包含文件和行号。
2. Verdict：APPROVE_FOR_FREEZE、CHANGES_REQUIRED 或 BLOCKED。
3. 审查基线：分支、HEAD、本地 origin/main、工作树路径清单。
4. P2-6 后全部任务的实际顺序、类型和四项 readiness 状态。
5. OTA-DEC-001 至 OTA-DEC-012 的逐项一致性结论。
6. 已冻结来源及零差异结果。
7. 建议提交冻结的候选合同和提示词。
8. 测试命令、退出码、通过数、失败数和跳过数。
9. 白名单、生产源码、冻结文件、未跟踪文件和临时产物审计。
10. 残余风险和后续批准条件。
11. 明确声明本轮没有修改受审查文件、没有改变治理状态、没有 commit、push 或 merge。
12. 明确声明即使 Verdict 为 APPROVE_FOR_FREEZE，当前规范仍是 DRAFT_PENDING_REVIEW，决定仍是 PROPOSED，任务仍是 NOT_DISPATCHABLE。

如果没有 findings，必须明确写“未发现阻止提交冻结审批的问题”，并继续说明残余执行依赖和未运行测试风险，不能省略验证报告。
