# P3-6 治理变更批次（批次 1）证据

- 日期：2026-09-02
- 会话角色：主会话（治理变更执行）
- 批次范围：**仅治理记账**，不含任何产品代码或 CI 接线改动（CI 接线是批次 2）
- 基线 HEAD：`ded14e8cb476a98191bcaca2d9b83be71471f044`

本文件承载本批次全部哈希。原因：`Tools/provenance/manifest_profiles.json` 的
Governance profile `root_patterns` 只覆盖 `docs/ota-prompts/`，`docs/ota-exec-notes/`
不属于任何 profile，因此在此登记哈希不会触发「看板/合同指纹自指循环」。
看板 `PLAN-OTA-EXEC.md` 本身是 Governance `required_path`，其中只记录路径、
PR 号与结论，不记录任何哈希（含 commit SHA）。

## 1. 变更动机

P3-1 于 2026-09-02 收口合入 `main`（PR #12 产品与验收资产、PR #13 收口回写）。
其直接后果是两张卡的依赖前提发生变化，但看板 §8.1 readiness 矩阵仍停留在
P3-1 收口前的状态：

- `P3-4` 的 `dependency_state` 仍写 `BLOCKED_BY_DEPENDENCY: P3-1`，而 P3-1 已完成；
- `P3-6` 既缺 `prompt_path`（无派工书），其依赖描述又建立在「先接线必红」的旧前提上
  ——该前提随两套 BLE 测试文件成为跟踪文件而消失。

`tests/ota/test_acceptance_bundle.py` 中
`test_readiness_matrix_mirrors_board_order_and_derives_dispatch` 把可派单集合
钉死为 `{P3-1, P3-2, P4-2}`。这是**刻意的精确受控**设计：任何可派单集合的扩大都
必须作为治理变更显式登记，不得由实现顺手放宽。因此本批次必须四件事同批完成，
缺一即为不自洽。

## 2. 变更清单（4 个文件）

### 2.1 新增：`docs/ota-prompts/prompt-P3-6-implementation.md`

- 大小 9083 B，纯 LF（CRLF=0，bareLF=112）
- SHA-256 `0aee80d90eee9e267baee7f6d74ddf4bf0bda0fee7f155b675aeb3b49c827209`

**行尾为纯 LF 并同批追加 `.gitattributes` 护栏**，是实测决定而非风格偏好。
`docs/ota-prompts/` 是 Governance profile 的 `root_patterns` 成员，新文件属**本轮新增
的 manifest 绑定路径**，其工作树字节必须在任意克隆上逐字节稳定。逐路径实测索引 blob
与工作树字节：

| 路径 | 索引 blob | 工作树 | 一致 | 护栏 |
| --- | --- | --- | --- | --- |
| `docs/ota-prompts/prompt-P3-1-implementation.md` | 7305 B 纯 LF | 7430 B 纯 CRLF | 否 | 无（既存隐患） |
| `docs/ota-prompts/prompt-P2-6-SD-R5-independent-review.md` | 4382 B 纯 LF | 4382 B 纯 LF | 是 | 已有 `-text` |
| `PLAN-OTA-EXEC.md` | CRLF=705 保留 | CRLF=706 | 逐字节往返 | 不需要 |
| `.github/workflows/firmware-build.yml` | CRLF=245 保留 | CRLF=245 | 逐字节往返 | 不需要 |
| `tests/ota/test_acceptance_bundle.py` | 96495 B 纯 LF | 98786 B 纯 CRLF | 否 | 无（既存隐患，见下） |

初稿曾按「与 16 份 CRLF 兄弟文件一致」把派工书写成 CRLF，但那正好复现
`prompt-P3-1-implementation.md` 那一行的隐患：索引 LF、工作树 CRLF，Linux 克隆上
字节数差 112。改为纯 LF 后与 `prompt-P2-6-SD-R5-independent-review.md` 的既有护栏
先例完全一致：

```
/docs/ota-prompts/prompt-P3-6-implementation.md -text
```

按 `.gitattributes` 文件头明文的「只增不改」规约插在排序位（`P2-6` 之后），
`git diff --numstat` = `1 0` 纯新增。`git check-attr text` 复核为 `unset`。
`.gitattributes` 自身不在任何 profile、不被任何工具引用，实测追加后 P3-1 合同校验器
错误条数不变，故指纹中性。

**未一并修的既存隐患**：`tests/ota/test_acceptance_bundle.py` 是 Validation profile
`required_paths` 成员且同样索引 LF / 工作树 CRLF。此处**刻意不加护栏**——加护栏会改变
它的工作树字节，使 P3-1 已冻结的 Validation manifest 额外失效，属对已完成轮次的改判。
该项应另立卡与相关轮次一并处理。

内容要点：

- `## 权威合同` 只引用 `OTA-XC-BLE-LIFECYCLE`，**刻意不引用**
  `PROPAGATED_CONSUMER_CLAUSES` 的 7 条。原因：`test_acceptance_bundle.py` 要求
  凡引用传播条款的派工书必须同时出现在该条款的 `affected_tasks` 里，否则需改动
  接口矩阵——那属于另一类治理变更，不应与本批次混装。
- `## 任务类型` 取值 `IMPLEMENTATION`；`## 阻断性决策` 为「无。」，不含
  `OTA-DEC-\d{3}`。
- 全文不含 `TASK_STATUS_FIELDS` 字段名，也不含 `TASK_STATUS_VALUES` 取值
  （含裸 `READY` / `FROZEN` / `SATISFIED` / `DISPATCHABLE`），避免派工书成为
  任务状态的第二处事实源。已用 `prompt_task_status_value_violations` 的本地复刻
  逐条扫描确认 0 命中。
- 唯一任务状态出处以 `PLAN-OTA-EXEC.md` readiness 矩阵为准，派工书内显式声明
  「本文件不得另行维护该状态」。

### 2.2 修改：`PLAN-OTA-EXEC.md`

- 变更后 393305 B（变更前 391273 B），CRLF=705（不变），bareLF 241 → 244
- `git diff --numstat` = `9 6`
- 变更后 SHA-256 `5202c7a307a6c14418726d3e3a8da384346e2657bf328e71f89b8ef6b49817c5`

该文件是 CRLF 正文 + 裸 LF 追加区的混合行尾文件，Edit/Write 工具会把行尾归一化
从而混入上百行伪变更。因此 8 处改动全部通过 `.cache/p36/edit_board.py` 以
`read_bytes` / `write_bytes` 字节级完成，每处带命中计数断言，写回前断言
`CRLF 不变`、`bareLF 恰好 +3`、`U+FFFD 计数为 0`。

8 处改动：

1. §8.1 前言：可派单集合由 `P3-1/P3-2/P4-2` 改为
   `P3-1/P3-2/P3-4/P3-6/P4-2`，并说明解除原因与 §9 登记指向。
2. P3-4 行：`BLOCKED_BY_DEPENDENCY` → `SATISFIED`，`NOT_DISPATCHABLE` →
   `DISPATCHABLE`，`dispatch_reason` 相应改为
   `FROZEN_DECISIONS_AND_DEPENDENCIES_SATISFIED`。
3. P3-6 行：填入 `prompt_path`，清空 `spec_block_reason`（两者严格 XOR），
   依赖态与可派单态同步。
4. P3-6 任务卡「状态」行：追加治理记账说明。**状态取值仍为 `待办`**——看板 §0
   第 10 条把状态钉死为 `待办/进行中/阻塞/完成` 四值，可派单不等于已认领。
5. P3-6 任务卡「依赖」行：改写为「已于 2026-09-02 满足」，并明确记录
   「先接线必红」的旧前提已消失。
6. P3-6 任务卡「注意」行：追加同批治理变更说明。
7. §9 变更登记表：新增一行，记录冲突点、提议、用户授权范围与「已执行」。
8. §10 会话日志：按最新在前追加一行。

`dispatch_eligibility` 由测试从 `content_readiness` + `dependency_state`
**推导**，不是人工填写；上述 2/3 两处的可派单态是推导结果与人工列的一致性对齐。

### 2.3 修改：`tests/ota/test_acceptance_bundle.py`

- 变更后 98786 B，CRLF=2139，bareLF=0
- `git diff --numstat` = `5 1`
- 变更后 SHA-256 `3ff994cca9e088113c67f71f9c64d500a4a772cbaa2fedb17c01af279644ca88`

断言由 `{"P3-1", "P3-2", "P4-2"}` 改为 `{"P3-1", "P3-2", "P3-4", "P3-6", "P4-2"}`，
并把失败信息改写为说明「P3-1 收口合并解除 P3-4/P3-6 阻塞属治理变更，须与派工书
同批登记 §9」。

**刻意保持等值比较（`assertEqual`），没有放宽成子集断言。** 放宽会让今后任何
可派单集合扩大都不再需要治理登记，等于把本批次要建立的门禁自己拆掉。

行尾说明：该文件 HEAD 索引 blob 为纯 LF（96495 B / 2135 bareLF），工作树为纯
CRLF（98786 B / 2139 CRLF），属 `core.autocrlf=true` 的既有检出状态，**不是**本次
编辑造成的污染。佐证：`git diff --numstat` 仅 `5 1`，且对 diff 全量扫描「内容相同
仅行尾不同的 del/add 配对」得 0 对。

### 2.4 修改：`.gitattributes`

追加一行 `-text` 护栏（内容与理由见 §2.1）：`git diff --numstat` = `1 0`，纯新增，
未改动任何既有条目。

## 3. 本地验证

### 3.1 治理门禁全量

```
$ python tests/ota/test_acceptance_bundle.py
Ran 65 tests in 40.620s

OK
```

### 3.2 待接线的两个 BLE 测试（批次 2 的接线目标，此处仅确认标记稳定）

```
$ python tests/ota/test_ota_ble_frame.py
=== summary: 39 checks, 0 failure(s) ===
P3_1_BLE_FRAME=PASS checks=39 failures=0

$ python tests/ota/test_ota_ble_session.py
=== summary: 105 checks, 0 failure(s) ===
P3_1_BLE_SESSION=PASS checks=105 failures=0
```

两个 marker 与派工书验收判据中钉死的字符串逐字一致。

## 4. 对 P3-1 冻结合同的影响（如实申报）

本批次改动落在两个 profile 的绑定路径上，因此在**当前工作树**上复跑 P3-1 的
冻结合同校验器必然变红。实测：

```
$ python Tools/acceptance/validate_bundle.py     --contract docs/acceptance-contracts/P3-1-v2.contract.json     --matrix docs/acceptance-contracts/P3-1-v2/P3-1-v2.evidence-matrix.json     --repo-root .
ERROR: input manifest worktree length mismatch: tests/ota/test_acceptance_bundle.py
ERROR: input manifest worktree SHA-256 mismatch: tests/ota/test_acceptance_bundle.py
ERROR: input manifest is missing worktree files for Governance: docs/ota-prompts/prompt-P3-6-implementation.md
ERROR: input manifest worktree length mismatch: PLAN-OTA-EXEC.md
ERROR: input manifest worktree SHA-256 mismatch: PLAN-OTA-EXEC.md
VALIDATION=FAIL errors=5
```

`errors=5` 恰好等于本批次 3 个文件的指纹足迹，**没有多出任何一条**：

| 来源 | profile | 错误条数 |
| --- | --- | --- |
| `tests/ota/test_acceptance_bundle.py` 改字节 | Validation（`required_paths`） | 2（length + SHA-256） |
| `docs/ota-prompts/prompt-P3-6-implementation.md` 新增 | Governance（`root_patterns`） | 1（缺失路径） |
| `PLAN-OTA-EXEC.md` 改字节 | Governance（`required_paths`） | 2（length + SHA-256） |

这条「错误条数与改动清单精确对账」本身就是夹带检测：多出任何一条都说明本批次
混入了未申报的改动。

判定：这是**已确立的治理漂移模型**，不是回归。P3-1 轮次的可复现性由其收口锚定
提交承载（在该提交的全新检出上复验为绿），不由持续演进的 `main` 承载；已 PASS 的
轮次不因后续演进被改判。同一模型此前已在 P2-6-v3 与 P3-1 收口回写上生效。

**批次 2 会新增第 3 条 profile 漂移**：`.github/workflows/firmware-build.yml` 是
Production profile 的 `required_paths` 成员，接线两行会使 Production manifest 也
变化，届时 `errors` 将由 5 增至 7。这一点在批次 2 的证据笔记中另行申报。

## 5. 边界声明

- 本批次**未**改动任何产品源码、CI 工作流、既有验收合同或证据矩阵。
- 本批次**未**追溯修改 P3-1 的合同与证据矩阵（禁止改判已完成轮次）。
- P3-6 将携带自己的新 `task_id` 验收合同，不复用也不篡改 P3-1 的。
- P3-6 的独立验收必须由非实现会话执行；本会话作为实现方不得自验收。
- 6 个刻意排除的未跟踪文件保持未跟踪：`.cache-cmake-time-test.cmake`、
  `.claude/cc_recover_s4.js`、`.claude/ccprobe_hash.js`、`.claude/ccprobe_plan.js`、
  `.claude/write_r5_phase0_board.py`、`.claude/write_r5_ruling_board.py`。
- 临时脚本 `.cache/p36/edit_board.py` 落在仓库内已忽略目录，不入库。
