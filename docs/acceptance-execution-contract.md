# 验收执行合同

版本：v3（2026-09-06，git 对象冻结；组件依赖、原始证据复用与批量审查）

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

合同必须包含以下三个基础输入组。旧合同仍按这三个组保守判定；新合同可额外引用
冻结 profile 配置中已审批的组件组，不能在执行时临时缩小范围：

| id | profile | category |
|---|---|---|
| `production` | `Production` | `production_source` |
| `validation` | `Validation` | `validation_inputs` |
| `governance` | `Governance` | `governance_inputs` |

三个基础输入组缺任意一项都不能冻结合同。fixture、工具链、硬件和环境状态使用
`external_inputs` 单独记录 fingerprint、证据路径及证据 SHA-256。

每个输入组**只能**包含 `id`、`profile`、`category` 三个字段。输入组按 profile 引用 git
对象，不再生成、不再绑定任何工作树字节 manifest；出现 `manifest_path`、`manifest_sha256`
等残留字段时校验器必须拒绝该合同。

每项判据的 `input_groups` 必须只列出其直接依赖的最小集合，且不得重复。产品输入对应
`production` 或 production_source 组件组；仓库内验收 runner/探针参与采集或解释观测时，
必须包含 `validation` 或 validation_inputs 组件组。已由 production_source 覆盖的生产
构建入口无需再绑定 Validation，但它调用的验收探针仍须声明真实依赖。
确实检查规约/派单内容时再包含 `governance`。不得把三个 profile 作为模板默认值，也不得
为减少重跑而删掉真实依赖。只有没有仓库内 runner/探针参与结论的直接产品观测，才可只列
产品输入组；模板中的单组示例不是所有产品判据的通用依赖清单。

跨组理由必须写入判据的 `dependency_rationale`，不能只放在 `description` 或聊天中。
该字段说明每个组如何影响结论；“完整性”或“保险”不构成依赖理由。结构由校验器检查，
依赖是否完整、理由是否真实仍由合同审批审查，不能靠一段非空文本自动证明。

| 判据字段/情形 | 合法情况 | 非法情况与校验错误 |
|---|---|---|
| `input_groups` | 非空、无重复、仅引用合同内已定义的基础或组件组 | 空/类型错/未知 ID，或 `input_groups must not contain duplicates` |
| 单输入组 | 可省略 `dependency_rationale` | 一旦提供就必须是非空字符串，`null`、空白、非字符串均报 `dependency_rationale must be a non-empty string when set` |
| 多输入组 | 必须提供非空字符串 `dependency_rationale` | 缺字段时报 `dependency_rationale is required when multiple input_groups are used` |

例如宿主测量判据应声明 `input_groups: ["production", "validation"]`，并解释
`dependency_rationale: "production 提供被测实现，validation 提供计算观测值的 runner"`。
反例是把该判据删成只有 `production` 来避免 runner 修改后重测，或无理由绑定全部三个组。

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

组件合同还要求所有 `commands` 声明 `input_groups` 和 `runner_paths`。前者列出命令真实
依赖的组，后者列出仓库内入口脚本与直接/间接助手的 POSIX 相对路径；直接工具观测无仓库
runner 时显式填空数组。判据必须包含其全部命令的依赖，不得把产品观测改标 `process`
以逃避产品输入。校验器检查依赖并集、runner 的冻结路径覆盖和命令文本中的脚本入口；
传递依赖与判据分类的真实性仍须非实现会话审查，路径声明本身不是可信证明。
runner 可由命令声明的任一受管组覆盖，包括生产构建入口；不能因 category 名称重复绑定
同一份已受管输入。组件合同的解释器命令不得省略 runner_paths，脚本/模块入口必须在其中；
解释器只支持显式脚本/模块入口与受限启动选项，不支持 -c/-Command/-EncodedCommand、
attached -c、node eval、bash -lc 等内联执行；未知选项 fail-closed。应使用已入库入口或
保守的基础组三组合同，不得以无关 runner 名称为内联代码背书。

## 4. 证据矩阵 v2

每项判据必须记录：

- `result`：`PASS`、`FAIL` 或 `NOT_OBSERVED`。
- `execution`：本轮执行使用 `EXECUTED`，合法复用使用 `REUSED`。
- `reused_from_round`：只有 `REUSED` 时填写原始实测轮次 ID，旧单跳记录为上一轮 ID。
- `origin_contract_sha256`、`origin_matrix_sha256`：新建复用记录必须绑定原始实测合同与
  矩阵文件哈希。组件合同强制这两个字段；旧三组单跳记录兼容保留，但无原始绑定不能升级
  为多轮复用。非 REUSED 记录两字段须省略或为 null。
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

基础和组件 profile 的范围由冻结 tree 内的 `Tools/provenance/manifest_profiles.json`
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

### 5.1 组件范围与防漏验

冻结配置提供 `Firmware`、`Flutter`、`Cloudflare`（生产输入），以及 `Capture`
（J-Link/截图采集工具）、`Evidence`（离线证据工具）。基础 Production 仍覆盖全部产品，
作为依赖未拆清时的保守后备；固件判据应避免无条件依赖 Flutter 页面。

在三个基础组之外可声明组件组，例如：

```json
{"id":"capture","profile":"Capture","category":"validation_inputs"}
```

组件 profile 必须在冻结配置中定义 category、目录边界、精确文件和非空 required_paths。
未知 profile、空范围、必需文件缺失、category 不符、runner 未覆盖均拒绝冻结。新增 runner
先将入口、导入模块、命令文件、fixture、解释器配置纳入受审依赖，再冻结合同。现有 Capture
并不自动覆盖其他目录的任务 harness；不得移动脚本或删除真实依赖来缩小复验范围。
依赖不清时使用保守组或停止请求裁定，不允许未跟踪/忽略目录中的验证代码作为隐式输入。

构建、原始采集、离线解析、封包应拆成独立判据和命令，消费的上游产物仍须绑定路径和
SHA-256。只换解析器必须重新解释原始字节，不能照抄旧 observed；采集缺失、污染或采集
实现变化才重采。共享 runner/产物必须声明共享依赖。旧合同不会自动变窄，须升版本审批。

新合同冻结前，审批者必须一次核对“变更组件 → 共享依赖 → 消费判据/命令”的影响范围。
若一个局部改动会使多数判据失效，先确认是否错误地绑定了整个 Production/Validation；
可以用现有受审组件表达时应拆清，确有共享依赖或范围尚不明确时保留保守组并说明理由。
不得追求更小重跑清单而漏掉公共头文件、链接/构建配置、传递调用或测量方法。此核对写入
现有 dependency_rationale/审查记录，不另建逐文件审计体系，也不回改历史冻结合同。

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
又没有可读取的仓库时，校验器必须拒绝判定（fail-closed），不得默认“未失效”。上一轮判据
须为可验证的 `EXECUTED PASS`，或能按 §6.1 追溯原始实测并通过历史核对的 `REUSED PASS`。
上一轮非 PASS、所引用的 profile 内容或定义变化、判据变化或所引用的执行定义变化时，
该判据必须重跑；缺来源包或中间计划则先补证据，不自动授权重采。另一项判据失败、
未引用的 profile/外部输入/命令/产物变化，不应扩大范围。

失效粒度是选用的 profile，而不是文件白名单。声明基础 `validation` 的判据仍会因 Validation 内任意
受管文件变化而保守失效；多组理由不会改变这个算法，更不能据此人工覆盖计划。共享命令、
产物或原始观测的判据并非独立，冻结合同前必须让依赖范围覆盖这些共享输入。回归测试须
同时证明“无关组变化只重跑其消费者”和“真实 runner 依赖变化仍重跑相应产品判据”。

不同 `task_id`、修改合同但不升版本、跳过版本或 `parent_contract_sha256` 不匹配时，禁止
生成复用计划，不能退化为“人工确认可复用”。

计划生成后，将上一矩阵文件 SHA-256、`rerun-plan.json` 路径及其文件 SHA-256 写入当前
矩阵，再去掉 `--write-rerun-plan` 重跑同一条命令完成最终校验。最终校验会重新计算计划并
要求 JSON 内容逐项一致，缺文件、错误哈希或人工改写计划都会失败。
`--write-rerun-plan` 只输出计划与 `FINAL_VALIDATION=NOT_RUN`，不是最终验收通过。

矩阵使用 `REUSED` 时，校验器还会核对观测值、证据哈希、命令记录和产物哈希与上一轮
一致。当前和上一矩阵文件哈希及 `round_id` 必须不同。多轮复用只允许直接锚定原始
`EXECUTED PASS`，不把中间 `REUSED` 当作一次新实测，也不因曾复用就强制重新采集。
当前证据包仍须包含复用后的决定性证据和产物。

### 6.1 原始执行锚点与历史核对

生成计划及最终校验时，传入原始执行和所需中间轮次，每份一对参数：

```powershell
python Tools/acceptance/validate_bundle.py --contract <current-contract> --matrix <current-matrix> `
  --repo-root . --previous-contract <previous-contract> --previous-matrix <previous-matrix> `
  --reuse-source <original-contract> <original-matrix> `
  --reuse-source <intermediate-contract> <intermediate-matrix> --write-rerun-plan rerun-plan.json
```

计划的 `reuse_origins` 给出原始轮次与合同/矩阵 SHA-256，按它填写当前矩阵的 origin 字段。
`previous_matrix_sha256` 仍绑定实际上一轮，禁止跳过失败轮次、挑历史最好结果冒充上一轮。
校验器只读核验原始包实物、输入身份、命令/产物定义、观测值与哈希，以及中间轮次自身的
前驱、计划和复用合法性；每个矩阵 SHA 在一次校验中只检查一次。缺来源包、缺计划、篡改、
自引、循环、同轮次或超过 128 层均 fail-closed。128 是解析安全上限，不是执行配额。

上一轮真实 FAIL 或 NOT_OBSERVED 不能由更早 PASS 恢复，无效中间轮不能洗白失败。真实
输入、门禁或观测方法变化仍须复测。历史证明仅作机器只读核验，不重建旧固件、不重跑旧
测试，也不要求 agent 逐轮重写报告；缺证据优先补证据，不能为省整理而重新采集。
最终包应携带所需来源合同、矩阵、计划和决定性证据，保证独立复校。

## 7. Harness 与性能门禁

- harness 结果必须由原始观测计算，禁止常量 PASS、预填成功字段或以没有错误日志代替
  成功证据。
- 缺日志、超时、解析失败、地址漂移和进程异常必须 fail-closed。
- harness 至少包含一个证明判据具有鉴别力的负例或故障注入。
- 性能门禁只能来自 `product_sla`、`safety_ratio` 或 `protocol_contract`。
- 历史测量值只能作为基线或告警阈值，不能加极小余量后变成阻断门槛。

## 7.1 阶段化执行与最小重跑

验收执行必须按“前置检查 → 产品观测 → 证据封包”三阶段推进。冻结合同的
`commands[].description` 应说明阶段、前置条件和共享输入；硬件/高成本命令还须写清
超时、观测配额、允许的恢复动作及重试条件。派单只解释这些约束，不能另增授权。
这些执行约束需审批和执行者核对；当前校验器不会代替调度器执行命令或自动计数硬件配额。

1. **前置检查（preflight）**只验证工具、连接、固件身份、目标状态、RTT/日志通道和
   输出目录等可执行条件。硬件 preflight 默认只读；若目标必须暂停 WDT 或写入调试域寄存器，
   合同必须明确地址、值、非持久性、恢复方式和授权。烧录、擦除、写 SD 属于另行授权的
   部署/产品命令，不得伪装成免费预检。若需部署目标镜像，先核对工具、连接和操作边界，
   按合同部署后再核对固件身份，不能要求一个尚未部署的镜像先通过身份检查。
   preflight 必须有明确超时和 fail-closed 结果；失败分类为 `HARNESS_FAIL` 或 `ENV_BLOCKED`，
   不消耗产品观测配额。只有相关前置条件满足，才能启动对应的部署或观测命令。
2. **产品观测（product）**只在相应 preflight 通过后执行。未约定重试时默认只执行一次；
   首次失败先保留证据和分类，不得换路径、换目录盲重试。在已有授权和剩余配额内，已提交的
   产品/harness 修复或有证据的外部状态变化，可以按重新计算的 rerun plan 最小范围复测。
   没有实际修复/状态变化时不得碰运气重试；配额耗尽或需要新操作时先申请授权，必要时升级
   合同。产品失败只能归类为 `PRODUCT_FAIL`，不能用 harness 修复掩盖。
3. **证据封包（evidence）**只整理已产生的原始输出、产物和哈希。封包或解析失败归类
   为 `HARNESS_FAIL` / `EVIDENCE_GAP`，只修复受影响的证据链；不得因为封包失败而重跑
   已通过且输入未变的产品观测。原始日志缺失、污染或测量工具不可信时，必须重新采集受影响
   的观测；失败分类本身不能把无效证据变成可复用 PASS。

下一轮必须先运行校验器生成 `rerun-plan.json`，只重跑 `required_commands` 所列的观测/采集
命令，并重新生成 `required_artifacts`。必要的只读预检、证据整理和完整性校验仍可执行，但
不得借这些阶段的名字绕过观测配额。未列入 `rerun_criteria` 的 `EXECUTED PASS` 判据应使用 `REUSED`；
若它的全部命令已因其他失效判据进入 `required_commands`，可消费同一次执行的真实输出，
不得为它再跑一次共享命令或夹带其他未计划命令。判据与命令不得复制新 ID 来绕过这一限制。
禁止以“方便”或“保险”为由重跑整套宿主测试、构建或硬件流程。只有生产输入、外部输入、
判据定义、命令定义、产物定义实际变化，或先前观测不是可复用 PASS 时，才扩大重跑范围。
**rerun plan 只计算失效范围，不授予操作权限或追加配额。** 验收报告必须记录本轮阶段、
失败分类、修复/状态变化证据、已消耗及剩余配额和 rerun plan，便于审计是否发生无授权重试。

首次正式轮次之后，生成计划和最终校验都须传入实际上一轮的 `--previous-contract` 与
`--previous-matrix`，即使本轮没有 REUSED；无复用时矩阵的三个 rerun 绑定字段仍按 §4 为 null。
最终校验会拒绝本可复用却新增计划外命令的 `EXECUTED PASS`。新的 FAIL/NOT_OBSERVED 必须
如实记录，不能因为旧 PASS 或减少轮次而删除；接收失败记录不表示追认计划外操作。
不得靠省略前轮参数、换任务/轮次 ID 或只运行计划生成模式规避检查。校验器不能自行发现
未提供的执行历史，也不调度命令或计数物理操作，执行者与独立验收者仍须核对完整账目。

### 7.2 执行效率与验收责任

- 实现者负责真实实现和自测，非实现会话负责独立验收；自测通过不等于正式 PASS。
- 派单前一次性审查依赖、门禁来源、负例、前置条件和配额。稳定硬件能力按工具链/设备/
  固件身份指纹复用；烧录、复位或换连接后仍需轻量核对当前身份、RTT 签名和 WDT 状态。
- 门槛只能来自已批准 SLA、协议或安全比例，不得用 917 ms 一类历史值加微小余量反向定门槛。
  更改门槛须审批并升级合同，不能为“省时间”放宽后追认 PASS。
- 保留一份失败原始输出、分类、根因/修复与重跑计划即可，不要求每轮另建完整审计套件。
  同一观测默认只跑一次；重试必须有修复或状态变化且在剩余配额内。换目录、换 agent、
  换轮次不得重置总配额。连续同因失败或配额耗尽时只暂停受影响动作，不拉起无关全量回归。
- 治理/文档/封包器修改优先用宿主正反例和静态检查验证，不因此重开已完成的产品卡。
  但 CI 接线、必要负例、真实日志/产物哈希及缺失判据不能省略。

必须回归：封包变动不重采、采集器/产品变动必须重采、遗漏依赖被拒、多轮原始 PASS 可复用、
原始证据篡改/中间计划缺失/失败洗白/循环均被拒；计划外成功执行被拒、计划内共享命令
不重复运行、新失败可记录、计划生成不冒充最终验收。测试入口为
`python -X utf8 -B tests/ota/test_acceptance_efficiency.py`，串行执行并将临时目录限定在项目内。

### 7.3 批量审查与正式验收准入

默认节奏是“集中审查 → 问题汇总 → 批量修复与局部自测 → 稳定基线正式验收 → 最小复验”。
这里的集中审查只覆盖本卡已知范围和当前可验证项，不要求穷举所有未来缺陷，也不增加一个
反复审批的前置验收工程。每修一个点就跑针对性单测是正常开发，不算重开正式验收轮次。

1. **集中预审**：派单者/非实现审查者一次核对契约与 SLA、受影响调用链和源登记、共享
   依赖、历史同类故障、harness 正反例、环境/输出边界及操作配额。检查全部当前可安全
   检查的相关项，不得发现第一个普通问题就结束审查并要求返工；无法检查的项注明原因。
   安全风险、越权或证据污染只暂停受影响动作，其他独立安全的检查继续，不能继续危险实测。
2. **一份清单**：在既有 research/证据文档汇总 `发现ID | 依据/判据 | 影响范围 | 处置 |
   自测证据`，区分本卡阻断、非阻断建议和范围外事项。已违反 required 判据、证据可信度或
   安全授权的缺陷不得降级成建议；风格偏好和无关存量债务不得成为重开本卡的理由。
3. **批量整改**：实现者对同根因的范围内调用点、配置与测试一起检查和修复，再交付一个
   自测完整的批次。不得每改一个文件/问题就要求重新派验收、冻结合同、提交或烧录。小范围
   单测、静态检查、增量编译可随修随跑；正式观测和硬件动作无论叫调试还是自测，都受原
   授权与累计配额约束。新增范围或安全风险先裁定，普通范围内缺陷不自动暂停整卡。
4. **正式验收准入**：本批已知阻断问题须有修复和针对性自测，受影响宿主回归通过，已能
   执行的环境前置检查完成，必要依赖/负例/操作计划已确认，才提交稳定批次进入正式验收。
   不得用昂贵正式验收代替这些开发检查。尚需首次真实产品观测才能判定的项应明确列入
   正式计划，不得为了准入要求它们提前“通过”，也不得伪造预检或宣称自测等于独立 PASS。
5. **集中反馈与复验**：独立验收在同一基线上完成安全可执行的相关检查，再一次反馈全部
   已发现问题与未覆盖项；有前置阻断的下游高成本命令暂不执行。整改后检查整个整改批次，
   只重验受影响项，不重新审计所有无关文件或重建历史证据。后续新发现注明新观测、回归
   或前次遗漏，并检查范围内同类问题；不能压下真实缺陷来维持“一轮通过”。

红线违反先作废被影响的结论，保留原始失败记录，再按依赖重算范围。只有公共基线、共享
工具或证据整体不可信且有明确影响依据时，才能扩大到整组/整卡；不得把“整卡作废重来”
作为任何问题的默认处罚。改变合同、授权或安全红线仍须先审批，不能借批量整改自行放宽。

跨 agent 问答与整改反馈必须遵守 `docs/agent-collaboration-contract.md`：沿用稳定问题 ID，
区分必修缺陷、建议、harness/证据问题和范围裁定；答复给出依据、首选最小改法及入口、
不可改变的约束、可执行验证与正反判据、责任人和下一步。不能只说“继续排查”“不充分”
或让实现者反复重读整份规范。原因未明时给出有界鉴别检查及各结果对应的下一步，不猜根因。
验收侧指出具体函数、推荐设计和测试判据不损害独立性；代写产品修复则须披露角色变化，
受影响范围另由非实现者复核。沿用现有批次问题表，不为每次问答另开审批或全量验收。

Flutter 调试与取证经验见 `.agents/skills/e-track-flutter-debug/SKILL.md`。该 skill 不增加
CI/真机配额，也不改变历史冻结合同；新规范及 helper 使用宿主回归，不重开历史产品卡。

#### 7.3.1 开发自验入口不套用正式验收准入

开工时先确认可执行的 SDK/宿主、命令、输出边界及授权路径。Flutter 开发入口见
`docs/flutter-development-validation.md`：无可安全使用的本地 SDK 时，按 §7.3.2 的用户
预授权把已审查的 WIP 批次提交到专用验证分支运行开发检查；不要在没有运行反馈时反复
交付“整改完成”或对相同输入重开静态审查。单次集中静态预审仍可进行，缺口须如实保留。

经用户明确授权的开发验证提交/推送不以测试已绿、实现稳定或合同已冻结为前置条件；
否则会形成“先有 CI 结果才能提交、先提交才能运行 CI”的循环。此例外只区分开发反馈
与正式验收；提交/推送/dispatch 的具体授权见 §7.3.2，不允许合并、发布、部署、烧录或真机操作，
也不绕过项目写入边界。规范要求 CI 不等于用户已经授权 CI 操作。

开发日志须绑定实际提交、宿主/SDK、执行范围、命令、退出码和原始输出，失败必须传递；
未执行项保持 NOT_RUN。分别记录源码整改、开发自验、构建验证和独立验收，开发自验不能
填为独立 EXECUTED PASS，也不消耗或虚构正式验收轮次。正式验收仍按 §5/§6/§7.1/§7.3
执行：实现及 runner 已提交、合同审批冻结、执行工作树门禁与 NOT_RUN 矩阵前检满足后，
再按校验器产生的 required_commands 执行。此澄清不修改历史冻结合同、profile 快照、
产品门槛或真机判据归属。

#### 7.3.2 实现 agent 的 Flutter 开发自测预授权

用户于 2026-09-09 明确要求为实现 agent 增加 Actions 自测及 APK 生成能力，并同步修改
项目规范。此决定作为持续有效、可撤回的范围内授权：实现 agent 可在独占的
`dev/flutter/**` 分支暂存/提交本任务改动、以 `Eitan-S-23` 推送该分支，并在该分支
dispatch/复跑 `flutter-dev-checks.yml`、读取日志或将产物下载到已预检的项目内目录。
复跑须有输入变化、新验证请求或已定位的环境恢复依据，先核对 workflow/ref，不能盲目重复失败。
无需每个整改批次重新申请相同授权，也不要求测试先绿或先满足正式验收准入。

用户于 2026-09-17 收窄自动打包触发：全部 `dev/flutter/**` 推送（包括原
`dev/flutter/apk/**`）只跑 analyze/test；只有显式 `workflow_dispatch` 且
`build_apk=true` 才请求 debug APK，APK 请求必须在双宿主跑完整测试。新开发 APK 保留
3 天，开发日志保留 14 天；上传前输出脱敏诊断，上传失败仍须如实保留。该规则不追溯
改变已有产物到期时间或历史证据。任何宿主失败都不能报告整体自测通过，debug APK
也不能替代 release-mode APK/EXE、真机或独立验收证据。不得使用生产签名/发布密钥。

共享工作树/索引不得并发切分支、暂存或提交；先建立项目内独占验证工作树，或由主会话
串行代办同一已授权动作。逐项审查暂存范围，保留无关脏文件；首跑可携带本次已交付的
开发入口与规范文件。禁止借机提交无关历史改动、修改远端/凭据、force-push、推主干/标签、
合并、调用生产发布工作流、部署、安装到真机、卸载/清数据、烧录或其他硬件操作。
这些仍需单独明确授权。权限不足、凭据缺失或网络故障须如实报告，不能绕过宿主沙箱。
用户后续明确禁止或更窄授权优先。本条不追溯修改旧记录，也不改变冻结合同或正式复验规则。

#### 7.3.3 实现与验收 agent 的开发产物清理预授权

用户于 2026-09-18 明确批准以下持续有效、可撤回的有界授权。实现与验收 agent 均可在
开发产物存储告警、上传配额错误或已确认的冗余开发 APK 积累时，按本条发起清理，
无需每批重复请示用户。它不改变实现/独立验收分离、任务状态、正式验收结果或产品判据。

- 唯一常规执行入口是 `Eitan-S-23/E-Track` 的可信 `main` 上
  `artifact-maintenance.yml`。目标必须符合已受审的
  `Tools/flutter/artifact_maintenance_policy.json`：指定开发工作流、`dev/flutter/**`
  来源、完整命名及仓库/提交/轮次身份一致的旧 debug APK。72 小时/分支滚动规则和固定
  保护 ID 不因本授权扩大；“不需要”不能由文件名、大小或 agent 主观推断。
- 先 dry-run，并对照看板、当前实现/复核交付与冻结证据核对候选用途。仍在使用、待复核、
  固定保留、验收引用或用途不明的候选一律保留；实现者和验收者均不得删除对自己不利的
  证据。工具不会自动发现所有跨会话引用，不能以“未列入 pin”推定不再需要；保护项未在
  策略覆盖时先停止 apply，由主会话协调保护清单并走既有治理流程，不能自行解除保护。
- 在现有任务记录登记操作者、清理事件、候选/保留理由和 dry-run 来源，由主会话协调串行。
  手动 apply 必须传入已审 `approved_artifact_ids`；执行器重新计算的候选 ID 集合与之
  不同则在任何 DELETE 前拒绝，回到只读核对。不得自动接受扩大的新清单。
- 同一清理事件总计最多 50 个 ID；换 agent、run 或分批不能重置上限。零候选即停止；
  本次处理结束或达到上限后不得为追求额度恢复连续开批。计划外、超上限或其他类别的删除
  仍需用户单独明确授权。既有每日定时策略不因此扩围。
- 记录维护 run/策略提交、每个 ID、大小、理由、HTTP 回执、最终清单及确认释放量；项目内
  证据遵守写入预检。失败立即停止剩余删除；不确定 DELETE 仅只读核对，不盲重试。
  清理本身不算独立验收，不重开产品观测，也不证明上传或 CI 已恢复。
- 禁止借本条删除 run、原始日志、日志包、缓存、Release、APK/EXE 验证副本、其他仓库资产，
  修改计费/可见性/凭据、削弱上传失败或绕过可信入口。CI 计费阻断使入口不可用时上报
  主会话；本条不授权 agent 在本地伪造 CI 环境或自行调用 DELETE。用户另行明确授权的
  主会话本地清理只适用于该次固定边界，不扩为持续本地权限。

产物删除只减少当前占用及后续存储累计，不返还运行分钟或已累计存储用量，也不解除付款/
预算限制。账号额度未知时保持未知，不按仓库字节数猜测。具体命令、输入与错误矩阵见
`docs/flutter-development-validation.md` 的 Artifact Maintenance；后续更窄授权或禁止优先。

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
