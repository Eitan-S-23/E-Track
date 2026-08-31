# P2-6 后续 OTA Spec 整改后独立冻结复核报告

审查日期：2026-08-18
项目根目录：`D:\github\my\E-Track`
审查模式：独立、只读冻结复核
报告说明：本文件是用户明确要求写入的复核输出，不属于受审查候选集。

## 1. Findings

### BLOCKER

无。

### HIGH

无。

### MEDIUM

无。

### LOW

无。

## 2. Verdict

`APPROVE_FOR_FREEZE`

B-01、H-01、M-02 和 M-03 均已关闭。当前未发现 BLOCKER、HIGH 或 MEDIUM finding；轻量 Governance/静态检查全部通过，唯一跳过是本机 Windows symlink 权限不足。该结论只建议提交人工冻结审批，不代表已经批准、冻结、改变决定状态或允许派单。

## 3. 审查基线

| 项目 | 实际值 |
|---|---|
| 工作树 | `D:\github\my\E-Track` |
| 分支 | `main` |
| HEAD | `93a355d6cc0a22c63fccdea5dc934f196291c169` |
| 本地 `origin/main` | `93a355d6cc0a22c63fccdea5dc934f196291c169` |

已跟踪差异路径：

- `.github/workflows/acceptance-governance.yml`
- `PLAN-OTA-EXEC.md`
- `Tools/provenance/manifest_profiles.json`
- `tests/ota/test_acceptance_bundle.py`

受审查未跟踪候选路径：

- `docs/ota-cross-system-contracts.md`
- `docs/ota-spec-decisions.md`
- `docs/ota-prompts/prompt-P3-1-implementation.md`
- `docs/ota-prompts/prompt-P3-2-implementation.md`
- `docs/ota-prompts/prompt-P3-3-implementation.md`
- `docs/ota-prompts/prompt-P3-4-experiment.md`
- `docs/ota-prompts/prompt-P3-5-integration.md`
- `docs/ota-prompts/prompt-P4-1-implementation.md`
- `docs/ota-prompts/prompt-P4-2-implementation.md`
- `docs/ota-prompts/prompt-P4-3-implementation.md`
- `docs/ota-prompts/prompt-P4-4-integration.md`
- `docs/ota-prompts/prompt-P5-1-acceptance.md`
- `docs/ota-prompts/prompt-P5-2-acceptance.md`
- `docs/ota-prompts/prompt-P5-3-acceptance.md`

其他未跟踪路径为四个受保护文件、本地复核指令和本报告。已阅读实际 tracked diff、完整共享合同、完整决定登记和全部 12 张候选提示词，没有仅采信整改总结。

本轮新增的 tracked 语义差异仅位于 `tests/ota/test_acceptance_bundle.py` 的 Governance 断言；该文件由用户在复核开始前整改，本轮未修改。未发现 MCU、Boot、BLE、Flutter、Worker/API、D1、Admin、发布工具或生产 workflow 的语义性新增。

## 4. 任务顺序与 readiness

| 顺序 | task_id | type | content_readiness | governance_maturity | dependency_state | blocking_dependencies | dispatch_eligibility |
|---:|---|---|---|---|---|---|---|
| 1 | P3-1 | IMPLEMENTATION | NEEDS_DECISION | DRAFT_PENDING_REVIEW | SATISFIED | P2-1、P2-2 完成 | NOT_DISPATCHABLE |
| 2 | P3-2 | IMPLEMENTATION | NEEDS_DECISION | DRAFT_PENDING_REVIEW | SATISFIED | P2-1、P2-2 完成 | NOT_DISPATCHABLE |
| 3 | P3-3 | IMPLEMENTATION | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P3-1、P3-2 | NOT_DISPATCHABLE |
| 4 | P3-4 | EXPERIMENT | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P3-1 | NOT_DISPATCHABLE |
| 5 | P3-5 | INTEGRATION | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P3-1、P3-2、P3-3、P3-4、P4-2 | NOT_DISPATCHABLE |
| 6 | P4-1 | IMPLEMENTATION | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P4-2 | NOT_DISPATCHABLE |
| 7 | P4-2 | IMPLEMENTATION | NEEDS_DECISION | DRAFT_PENDING_REVIEW | SATISFIED | P0 门槛完成；明确不依赖 P4-1 | NOT_DISPATCHABLE |
| 8 | P4-3 | IMPLEMENTATION | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P4-2 | NOT_DISPATCHABLE |
| 9 | P4-4 | INTEGRATION | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P4-1、P4-2 | NOT_DISPATCHABLE |
| 10 | P5-1 | ACCEPTANCE | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P1-P4 全部完成 | NOT_DISPATCHABLE |
| 11 | P5-2 | ACCEPTANCE | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P1-P4 全部完成且具备 P5-1 主路径 | NOT_DISPATCHABLE |
| 12 | P5-3 | ACCEPTANCE | NEEDS_DECISION | DRAFT_PENDING_REVIEW | BLOCKED_BY_DEPENDENCY | P1-P4 全部完成且取得 P5-1/P5-2 结论 | NOT_DISPATCHABLE |

实际依赖保持 `P4-2 -> P4-1`、`P4-2 -> P3-5`；P4-2 不依赖 P4-1，P4-1 与 P3-5 无自动依赖。12 张提示词均只引用 PLAN readiness 行，并在单一 `## 阻断性决策` 章节中性引用决定 ID，没有复制任务级状态值。

## 5. OTA-DEC-001 至 OTA-DEC-012 一致性

| Decision | 状态 | 复核结论 |
|---|---|---|
| OTA-DEC-001 | PROPOSED | 一致：8B `E-Track\0` 严格映射、未知机型与硬件/布局错误分离。 |
| OTA-DEC-002 | PROPOSED | 一致：raw image identity、header-integrity digest 和 asset integrity 已分域；`.etu base_sha8` 保持 raw，ETSL/candidate 使用 header 双零摘要，向量要求两种 SHA8 不同。 |
| OTA-DEC-003 | PROPOSED | 一致：门槛、单调计时、nearest-rank P99、单参数组合统计均已传播。 |
| OTA-DEC-004 | PROPOSED | 一致：`appVersionCode` 范围、400/426、无资产泄露及 Flutter 终止语义完整。 |
| OTA-DEC-005 | PROPOSED | 一致：单 Range、sidecar、If-Range、206/416、24h partial 和整文件复核完整。 |
| OTA-DEC-006 | PROPOSED | 一致：正式版本正则、文件名、ASCII/长度及远端写入前失败规则完整。 |
| OTA-DEC-007 | PROPOSED | 一致：N/T、引用保护、cleaner 只产 manifest、双审批、隔离和 R2 删除边界完整。 |
| OTA-DEC-008 | PROPOSED | 一致：rehearsal/production 隔离、runId/snapshot、零生产副作用和 gate reset 已传播。 |
| OTA-DEC-009 | PROPOSED | 一致：依赖方向和 schemaVersion=2 fixture 边界一致，无循环。 |
| OTA-DEC-010 | PROPOSED | 一致：权威 manifest、逐字节验证、legacy 隔离和 fail closed 完整。 |
| OTA-DEC-011 | PROPOSED | 一致：24h 结果保存、永久 key tombstone、原子迁移、请求/Cron 竞态和稳定 409 结果已定义并具备规范向量。 |
| OTA-DEC-012 | PROPOSED | 一致：token v2 canonical、排他 expiry、v1 cutover 和 recovery 隔离完整。 |

所有决定仍为 `PROPOSED`。候选合同和提示词保留了决定阻断，没有把用户选择当成已经冻结的派单授权。

## 6. 冻结来源与生产基线

- `PLAN-OTA.md`：零差异。
- `docs/ota-binary-contracts.md`：零差异。
- `docs/acceptance-execution-contract.md`：零差异。
- 已冻结 P2-6 提示词：零差异。
- MCU、Boot、BLE、Flutter、Worker/API、D1、Admin、发布工具、构建脚本和生产 firmware workflow 源码：无语义性工作树差异。
- 未新增正式 versioned acceptance contract、D1 migration 实现、schema fixture 实现或验收探针。
- `PLAN-OTA-EXEC.md` 的非目标字节和 EOL 审计通过；候选改动限定在 readiness 区域。

## 7. 可提交冻结的候选

建议提交人工冻结审批的候选范围是 `docs/ota-cross-system-contracts.md` 与 12 张 `docs/ota-prompts/prompt-P3-1-implementation.md` 至 `docs/ota-prompts/prompt-P5-3-acceptance.md`。这只是审批建议，不是批准、冻结或派单许可；`PLAN-OTA-EXEC.md` 和 `docs/ota-spec-decisions.md` 继续仅作为状态与裁定审查来源，不因本报告改变状态。

## 8. 测试证据

主 Governance 命令：

    python -B tests/ota/test_acceptance_bundle.py -v

执行时 `TEMP`、`TMP`、`TMPDIR`、Python cache 和可控测试缓存均指向项目内本轮专用目录 `.cache/post-p2-6-independent-freeze-review-rerun-20260818-2`。

| 检查 | 结果 |
|---|---|
| Governance unittest | 退出码 0；总计 62；通过 61；失败 0；错误 0；跳过 1；耗时 61.734 秒 |
| 跳过原因 | `symlink creation is unavailable: [WinError 1314] 客户端没有所需的特权。` |
| `git diff --check` | 退出码 0；仅出现 Git 的 LF/CRLF 转换提示，无 whitespace error |
| `git diff --check -- PLAN-OTA-EXEC.md` | 退出码 0 |
| Markdown | 15 个候选/治理 Markdown 文件严格 UTF-8、围栏和尾随空白检查通过，0 错误 |
| JSON | 3 个既有 JSON 文件本地解析通过 |
| YAML | 使用本机既有 PyYAML 6.0.3 解析通过，未安装依赖 |
| 结构检查 | 12 readiness 行、12 唯一 decision、41 唯一条款、12 唯一候选 prompt；task_id/path/文件名/反向枚举通过 |
| 状态传播 | 12 行均为 NEEDS_DECISION / DRAFT_PENDING_REVIEW / NOT_DISPATCHABLE；提示词状态复制数 0 |
| manifest/workflow path | 候选共享合同、决定登记和提示词路径覆盖检查通过 |
| 依赖复核 | 结构化检查 0 错误；`P4-2 -> P4-1`、`P4-2 -> P3-5` 正确，P4-2 明确不依赖 P4-1 |
| M-02/M-03 机械断言 | 任务状态值/非法别名、raw/header SHA8 分域、永久 tombstone、24h 边界和三种 Cron 竞态向量均通过 |
| token golden | canonical UTF-8/LF 67 字节；HMAC hex `0e68d9df74ba873ffd8eb6d4b5dbff06a18dbce6381828cd26a21c069bd9bb35`；Base64URL `DmjZ33S6hz_9jrbUtdv_BqGNvOY4GCjNJqIcBpvZuzU` |
| metadata golden | compact insertion-order JSON、无末尾换行，1800 字节；SHA-256 `47d2ee8057313e5e556dc5d41159cb2e51bf766cf8b526de8bb30a3b5096fd85` |

新增治理测试实际执行并通过，已机械覆盖本轮整改的状态传播、摘要域和 Admin tombstone/Cron 竞态语义。

未运行 GCC、AC5、Flutter build、Worker deploy、D1 migration、模拟器、网络、真机、完整实验或正式验收，符合本轮限制。

## 9. 工作树、白名单与临时产物审计

- 四个受保护未跟踪文件在审查开始时存在，大小和 SHA-256 分别为：`.cache-cmake-time-test.cmake` 132B / `cdb645410538da5f203a26e506c3c253b0fedef38ed511a8b45ef3035fee6985`；`.claude/cc_recover_s4.js` 4347B / `bc60bdbc4699112f68a475f969c9abb96713135e4fb59b04b913155d61a6099b`；`.claude/ccprobe_hash.js` 2313B / `d52b898e2fdfdcf9b5771b2f4ef42e9e1f80ce86cd9a4b618744a1b5960a2d81`；`.claude/ccprobe_plan.js` 1948B / `ee0b319d4443959fd8c0c1ca3a7f71db59ffb141d22871bb811914b70cd624f4`。
- 本轮未执行、修改、移动或删除上述四个文件；结束审计的大小和 SHA-256 与开始记录完全一致。
- 本轮唯一测试缓存为 `.cache/post-p2-6-independent-freeze-review-rerun-20260818-2`，验证为空后已删除；根目录不存在 `.acceptance-repo-fixture-*`、`.acceptance-validator-test-*` 或 `.dispatch-scope-probe-*` 残留，也无相关 Python 测试进程。
- `.cache` 内其他既有忽略目录和产物均视为审查前资产，未复用、修改或清理。
- 本轮唯一主动报告写入为 `.claude/post-p2-6-independent-freeze-review-report.md`，由用户明确要求，不属于受审查文件；受审查文件在复核开始和结束时哈希一致。
- 未发现本轮主动选择的项目外写入；所有可控临时路径均位于活动项目根目录内。

## 10. 残余风险与后续条件

- B-01、H-01、M-02 和 M-03 已在候选合同、提示词和 Governance 断言中闭合；后续语义回归仍需通过同一治理套件和人工冻结审批发现与处理。
- P3-4 的真实实验、资产发布链、migration/backfill、部署和正式验收仍是后续执行 gate，本轮按指令未运行，不构成本次 Spec 冻结建议的新增缺口。
- Windows symlink 权限导致的单项跳过仍是环境能力缺口；它不改变本次建议，但正式冻结前应在具备 symlink 能力的治理环境验证该项。
- 本结论仍需人工冻结审批，也不会自动解除 execution gate、实验依赖或生产审批。

## 11. 操作声明

本轮没有修改任何受审查候选、生产源码、冻结合同、PLAN、决定登记或 Governance 文件；用户在本轮开始前已修改的 `tests/ota/test_acceptance_bundle.py` 仅作只读复核。没有改变 `PROPOSED`、`DRAFT_PENDING_REVIEW`、`NOT_DISPATCHABLE` 等状态；没有执行 commit、push、merge、fetch、stash、checkout、reset、restore、rebase、build、deploy、migration、模拟器或真机验收。除用户明确要求的本报告外，没有创建或修改审查输出。

## 12. 状态声明

本轮 Verdict 为 `APPROVE_FOR_FREEZE`，但当前共享规范仍为 `DRAFT_PENDING_REVIEW`，`OTA-DEC-001` 至 `OTA-DEC-012` 仍为 `PROPOSED`，P3-1 至 P5-3 仍为 `NOT_DISPATCHABLE`。该 Verdict 只表示建议提交人工冻结审批，不代表已批准、冻结或允许派单。
