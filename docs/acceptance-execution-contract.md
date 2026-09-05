# 验收执行合同

版本：v3（2026-09-05，git 对象冻结版）

本合同适用于 OTA、固件、模拟器、硬件闭环和其他需要独立验收的任务。v3 把验收标准、
输入依赖、执行命令、产物和观测值全部结构化，校验器必须读取实物复核，不能只检查 JSON
字段是否存在。

v3 的实质变化是：**跨轮输入身份不再用自研 manifest 记录工作树字节，而是冻结被验实现的
Git 提交、tree 和该 tree 内的 profile 配置 blob。** 两轮失效判定只比较 Git 对象，因此
检出行尾、`core.autocrlf`、mtime、绝对路径和 profile 外的提交不会制造跨轮噪声。最终验收
另有执行 worktree 门禁：冻结提交必须是当前 HEAD 的祖先，冻结后不得再有 profile 内提交、
脏文件或未跟踪文件。这样既不把操作系统检出差异当输入变化，也不允许拿旧提交给脏工作树
的产物背书。

v2 的稳定 manifest 本来就不包含 mtime、绝对 `RepoRoot` 或 HEAD；它的真实缺陷是最终校验
重新读取工作树字节、枚举 profile 内未跟踪文件，以及 Governance 包含每轮必改的看板。
自研生成器 `Tools/provenance/source_manifest.ps1` 与 `etrack-input-manifest-v2` 已删除，v2 合同
不再被当前校验器接受。

## 1. 权威来源与冻结

1. 每轮验收必须引用 `docs/acceptance-contracts/` 下的版本化 JSON 合同。
2. `.claude/` prompt、聊天消息和历史报告只能解释合同，不能成为唯一标准。
3. 冻结前必须先把实现提交进 `main` 或待合并分支，再把该提交的三个对象回填合同：

   ```powershell
   git rev-parse HEAD        # -> freeze_commit
   git rev-parse HEAD^{tree} # -> freeze_tree
   git rev-parse HEAD:Tools/provenance/manifest_profiles.json # -> profile_config_blob
   ```

   被验对象是这个提交，不是任意工作区状态。未跟踪实现或 harness 必须先提交，不能作为
   tree 外的隐式输入。
4. 合同置为 `FROZEN` 时必须记录审批人、审批时间、任务号和实现基线。先用 `NOT_RUN`
   矩阵运行一次校验器作为执行前检查；只有冻结提交可达、HEAD 未改变任何 profile 输入、
   profile 内无脏文件或未跟踪文件时才能开始执行合同命令。最终报告前再运行同一检查。
5. 验收开始后不得原地改变合同。新增或改变门禁必须提升合同版本并重新审批；harness 必须
   修改时也要先提交，并据此产生新冻结点和 rerun plan。
6. 最终合同、矩阵和紧凑证据先单独落成 `bundle_commit`。该提交可以晚于
   `freeze_commit`，但两者之间不得改变任何 profile 输入。
7. 再由后续收口提交向 `docs/acceptance-contracts/FREEZE-INDEX.md` 追加一行，登记
   `bundle_commit`、`freeze_commit` 与 `freeze_tree`。索引提交晚于证据包提交，避免让
   证据包记录自身 SHA；已登记行只增不改。
8. 合并 PR 只能使用保留原提交 ID 的 merge commit（或受控 fast-forward），**禁止
   squash 与 rebase-merge**。两者都会让 `freeze_commit` 从 `main` 不可达（P3-6 的
   `7833303` 即是先例），冻结包随之失去可复校的提交锚点。治理 CI 用完整历史核对索引中的
   `freeze_commit -> bundle_commit -> HEAD` 祖先链。
9. 轮次核验器是一次性资产，只对本轮负责；冻结包则是不可变审计资产，必须能在登记的
   `bundle_commit` 上自校验，但其结论只适用于合同的 `freeze_tree`。能否复用于后续 tree
   由 rerun plan 判定，禁止为了让历史核验器在 `main` 顶端变绿而回改冻结字节。

模板：

- `docs/acceptance-contracts/template.contract.json`
- `docs/acceptance-contracts/template.evidence-matrix.json`

最终校验：

```powershell
python Tools/acceptance/validate_bundle.py `
  --contract docs/acceptance-contracts/<TASK-vN>.contract.json `
  --matrix .acceptance-<task>/<round>/evidence-matrix.json `
  --repo-root .
```

同一命令在矩阵仍为 `NOT_RUN` 时是执行前检查，只核对合同结构、冻结对象和执行 worktree；
写入最终结果后再次运行，才会继续核对证据与产物实物。两次都必须通过。

## 2. 任务状态与验收结果

任务状态仍为 `待办`、`进行中`、`阻塞`、`完成`。单轮验收结果固定为：

| 结果 | 含义 | 对任务状态的默认影响 |
|---|---|---|
| `PASS` | 所有必选条件有有效证据并通过 | 可置 `完成` |
| `PRODUCT_FAIL` | 产品行为或产品产物不符合合同 | 保持 `进行中`，进入产品整改 |
| `HARNESS_FAIL` | runner、探针或验证工具不可信 | 保持原状态，只修验证工具 |
| `EVIDENCE_GAP` | 行为可能正确，但证据缺失或 provenance 不成立 | 保持原状态，只补相应证据 |
| `ENV_BLOCKED` | 当前环境或外部设备无法执行必需步骤 | 仅满足看板阻塞定义时置 `阻塞` |

验收者只追加验收人、轮次和结果，不得覆盖任务实现认领人。

## 3. 合同 v3 必填结构

合同顶层必须记录 `freeze_commit`、`freeze_tree` 与 `profile_config_blob`，三者都是 40 位
十六进制 Git 对象 id。校验器会核对 `freeze_commit^{tree} == freeze_tree`，并要求
`freeze_tree:Tools/provenance/manifest_profiles.json == profile_config_blob`；对象缺失、类型
不符、配置无效或任一关系不匹配都必须失败。

合同必须包含且只能包含以下三个输入组：

| id | profile | category |
|---|---|---|
| `production` | `Production` | `production_source` |
| `validation` | `Validation` | `validation_inputs` |
| `governance` | `Governance` | `governance_inputs` |

三个输入组缺任意一项都不能冻结合同。fixture、工具链、硬件和环境状态使用
`external_inputs` 单独记录 fingerprint、证据路径及证据 SHA-256。

每个输入组**只能**包含 `id`、`profile`、`category` 三个字段。输入组按 profile 引用 git
对象，不再生成、不再绑定任何工作树字节 manifest；出现 `manifest_path`、`manifest_sha256`
等残留字段时校验器必须拒绝该合同。

合同谱系必须 fail-closed。`version=1` 的 `parent_contract_sha256` 必须为 `null`；改变冻结
合同内容时，后继合同必须保持同一 `task_id`、版本严格加一，并用
`parent_contract_sha256` 绑定上一份合同文件。完全相同的冻结合同可跨多个验收轮次继续使用，
不得为了轮次变化虚增合同版本。

合同还必须定义：

1. `commands`：命令 ID、用途、精确命令文本、允许的退出码和是否强制保留输出。负例
   命令可以批准非零退出码，但实际命令必须与合同一致，退出码必须属于冻结的
   `expected_exit_codes`。
2. `artifacts`：产物 ID、用途和证据包内精确路径。
3. `criteria`：每项判据必须显式引用 `input_groups`、`external_inputs`、`command_ids`、
   `artifact_ids`，并定义可执行 gate。
4. gate：布尔门禁记录期望布尔值；数值门禁记录操作符、阈值、单位和依据；状态链门禁
   记录完整期望状态序列。

禁止保留未被任何判据引用的命令或产物定义，也禁止使用任意字符串表达失效范围。

## 4. 证据矩阵 v2

每项判据必须记录：

- `result`：`PASS`、`FAIL` 或 `NOT_OBSERVED`。
- `execution`：本轮执行使用 `EXECUTED`，合法复用使用 `REUSED`。
- `reused_from_round`：只有 `REUSED` 时填写上一轮 ID。
- `observed`：布尔值、带单位数值或实际状态链，必须能由校验器与 gate 比较。
- `evidence`：位于证据包内的原始证据文件。

矩阵顶层的 `previous_matrix_sha256`、`rerun_plan_path`、`rerun_plan_sha256` 在没有复用时
必须为 `null`。任一判据使用 `REUSED` 时三项都必须填写，分别绑定上一矩阵文件、当前
证据包内的 rerun plan 路径和该 plan 文件的 SHA-256。

最终 `PASS` 必须满足：

1. 所有 required 判据均为 `PASS`，实际观测值满足冻结 gate。
2. 每个 PASS 判据引用的命令均有记录，实际退出码属于合同允许集合。
3. 合同要求命令输出时，`output_evidence` 必须指向有 SHA-256 绑定的真实文件。
4. 每个 PASS 判据引用的产物都必须位于证据包内；校验器重新读取文件并核对路径边界、
   大小和 SHA-256。
5. 命令列表或产物列表为空时不得宣告最终 PASS。

本轮实际执行并得出 `PASS` 或 `FAIL` 的判据必须记录合同引用的命令及其输出。产品失败和
harness 失败还必须绑定实际参与判定的产物；不得仅凭一段手写失败说明宣告
`PRODUCT_FAIL` 或 `HARNESS_FAIL`。`NOT_OBSERVED`、证据缺口以及确实未产生下游产物的
环境阻塞可以不伪造产物，但必须保留原因和已有原始证据。

## 5. 输入组范围与枚举口径

三个 profile 的范围由冻结 tree 内的 `Tools/provenance/manifest_profiles.json`
（`etrack-manifest-profiles-v1`）唯一定义。合同用 `profile_config_blob` 绑定它；校验器必须
从每份合同自己的 `freeze_tree` 读取，禁止用当前 checkout 的配置重新解释历史 tree，也
禁止在合同或脚本里另写一份路径清单。

- Production 覆盖真实 GCC CMake 入口、链接配置、CI/打包脚本和生产源码，必须包含
  GCC CMake 实际引用的 `MDK-ARM_F435/RTE/Device/-AT32F435RGT7/**` 与
  `RTE/_X-Track/**`；AC5 专用 `RTE/_X-Track-App-AC5/**` 和旧 CGU7 输入不得混入，
  否则 AC5 侧改动会打红 GCC 判据。
- Validation 覆盖测试、runner、探针、校验工具以及两个合同模板的精确路径。
- Governance 覆盖 agent 规则、跨系统契约和本执行合同。

不得把整个活动合同目录纳入 profile，避免合同自引用和无关任务相互失效；当前版本化合同
由矩阵的 `contract_sha256` 单独绑定。

以下两个文件必须留在**所有** profile 之外，原因是它们每轮收口都会被回写：

- `PLAN-OTA-EXEC.md`：看板。留在 Governance 会让两轮之间任何一行会话日志改动打红整个
  Governance 组，使全部治理判据失去复用资格。
- `docs/acceptance-contracts/FREEZE-INDEX.md`：冻结点索引。它记录提交 id，进入 profile
  会构成自指环。

校验器枚举 profile 路径集时只读 git 对象：

```powershell
git -c core.quotepath=false ls-tree -r -z --name-only <freeze_tree> -- <pathspec...>
```

所有路径命令统一使用 `-z` 原样输出，并显式设置 `core.quotepath=false`；本仓库存在非 ASCII
路径（`Tools/图标/**`），不得解析 Git 的引号转义文本输出。路径集按 UTF-8 字节序排序，
避免不同 locale 下顺序漂移。

跨轮失效判定只读 Git 对象。校验器对每个 profile 要求路径集非空且包含冻结配置中的全部
`required_paths`；profile 定义本身改变时该组必须失效。mtime、检出行尾、绝对路径、证据
目录位置和 profile 外提交不参与这个判定。

执行门禁与跨轮失效判定是两件事。最终校验还会要求 `freeze_commit` 是执行 worktree HEAD
的祖先，比较 `freeze_tree` 与 `HEAD^{tree}` 的 profile 差异，并用 Git 的逻辑 diff 检查
tracked 改动、用 `ls-files -o --exclude-standard` 检查未跟踪输入。正常 `autocrlf` 检出仍是
Git clean，不会假红；真实脏源码、未提交 harness、profile 内未跟踪文件或冻结后提交的输入
变化必须失败。推荐始终在 `freeze_commit` 的专用干净 worktree 中执行验收。

## 6. 自动最小复验

需要复用上一轮证据时，先生成计划。两轮的 `freeze_tree` 在同一个仓库内比较，因此不再
需要上一轮的 worktree，只需要一个能解析两个 tree 的 Git 仓库：

```powershell
python Tools/acceptance/validate_bundle.py `
  --contract docs/acceptance-contracts/<TASK-v2>.contract.json `
  --matrix .acceptance-<task>/<current>/evidence-matrix.json `
  --repo-root . `
  --previous-contract docs/acceptance-contracts/<TASK-v1>.contract.json `
  --previous-matrix .acceptance-<task>/<previous>/evidence-matrix.json `
  --write-rerun-plan rerun-plan.json
```

校验器会先核对合同谱系，再对每个 profile 执行

```powershell
git -c core.quotepath=false diff-tree -r -z --name-only --no-renames --no-commit-id `
  <previous_freeze_tree> <current_freeze_tree> -- <pathspec...>
```

每轮 pathspec 来自该轮冻结的 profile 配置；若同一 profile 的定义改变，该组直接失效。
校验器还会比较 external input fingerprint、判据定义、命令定义、产物定义和上一轮判据结果，输出
`changed_input_groups`、`rerun_criteria`、`reusable_criteria`、`required_commands` 和
`required_artifacts`。两个 `freeze_tree` 相同即 tracked 输入字节相同：此时 commit id 变化
本身不触发跨轮复验，但最终执行门禁仍要求合同中的 `freeze_commit` 可达。两个 tree 不同而
又没有可读取的仓库时，校验器必须拒绝判定（fail-closed），不得默认“未失效”。上一轮不是
`EXECUTED PASS`、profile 内容或定义变化、判据变化或执行定义变化时，该判据必须重跑。

不同 `task_id`、修改合同但不升版本、跳过版本或 `parent_contract_sha256` 不匹配时，禁止
生成复用计划，不能退化为“人工确认可复用”。

计划生成后，将上一矩阵文件 SHA-256、`rerun-plan.json` 路径及其文件 SHA-256 写入当前
矩阵，再去掉 `--write-rerun-plan` 重跑同一条命令完成最终校验。最终校验会重新计算计划并
要求 JSON 内容逐项一致，缺文件、错误哈希或人工改写计划都会失败。

矩阵使用 `REUSED` 时，校验器还会核对观测值、证据哈希、命令记录和产物哈希与上一轮
一致。当前和上一矩阵文件哈希及 `round_id` 必须不同；被复用的上一判据必须由上一轮
实际 `EXECUTED`，不能继续复用一个 `REUSED` 结果。当前证据包仍须包含复用后的决定性
证据和产物，避免形成不可独立解释的链式引用或循环自证。

## 7. Harness 与性能门禁

- harness 结果必须由原始观测计算，禁止常量 PASS、预填成功字段或以没有错误日志代替
  成功证据。
- 缺日志、超时、解析失败、地址漂移和进程异常必须 fail-closed。
- harness 至少包含一个证明判据具有鉴别力的负例或故障注入。
- 性能门禁只能来自 `product_sla`、`safety_ratio` 或 `protocol_contract`。
- 历史测量值只能作为基线或告警阈值，不能加极小余量后变成阻断门槛。

## 8. 紧凑证据包

最终证据包必须包含冻结合同（含 `freeze_commit` / `freeze_tree` /
`profile_config_blob`）、最终矩阵、rerun plan（发生复用时）、命令输出、决定性原始日志、
最终产物和外部输入证据。所有路径必须位于矩阵
所在证据包内，且由 SHA-256 绑定。输入组不再产出 manifest 文件。证据包提交后，在下一次
收口提交中把 `bundle_commit` 与合同的输入冻结点登记到
`docs/acceptance-contracts/FREEZE-INDEX.md`；复校 checkout `bundle_commit`，不能 checkout
`freeze_commit` 后假定最终证据已经存在。

生成日志或计划前必须使用 worktree 输出守卫。目标文件或其任一父目录若为
symlink、junction 或其他 reparse point，必须在写入前拒绝，不能跟随链接覆盖 worktree
外或其他位置的文件。`--write-rerun-plan` 必须在创建父目录前检查一次完整父链，并在实际
写入前再次检查新建后的完整父链。

默认不保留完整构建目录、重复 checkout、源码副本和每轮重复日志。清理大文件前必须先
确认紧凑证据包能够独立解释结论。
