# 验收执行合同

版本：v2（2026-08-15，fail-closed 收紧版）

本合同适用于 OTA、固件、模拟器、硬件闭环和其他需要独立验收的任务。v2 将验收标准、
输入依赖、执行命令、产物和观测值全部结构化，校验器必须读取实物复核，不能只检查 JSON
字段是否存在。

## 1. 权威来源与冻结

1. 每轮验收必须引用 `docs/acceptance-contracts/` 下的版本化 JSON 合同。
2. `.claude/` prompt、聊天消息和历史报告只能解释合同，不能成为唯一标准。
3. 冻结前先生成三类 manifest。将 JSON 文件哈希回填 `manifest_json_sha256`，将 JSON
   内部稳定文件集合指纹 `ManifestSHA256` 回填 `manifest_sha256`，两者禁止混用。
4. 合同置为 `FROZEN` 时必须记录审批人、审批时间、任务号和实现基线。
5. 验收开始后不得原地改变合同。新增或改变门禁必须提升合同版本并重新审批。

模板：

- `docs/acceptance-contracts/template.contract.json`
- `docs/acceptance-contracts/template.evidence-matrix.json`

最终校验：

```powershell
python Tools/acceptance/validate_bundle.py `
  --contract docs/acceptance-contracts/P2-6-v1.contract.json `
  --matrix .acceptance-p2-6/<round>/evidence-matrix.json `
  --repo-root .
```

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

## 3. 合同 v2 必填结构

合同必须包含且只能包含以下三个 Git manifest 输入组：

| id | profile | category |
|---|---|---|
| `production` | `Production` | `production_source` |
| `validation` | `Validation` | `validation_inputs` |
| `governance` | `Governance` | `governance_inputs` |

三类 manifest 缺任意一项都不能冻结合同。fixture、工具链、硬件和环境状态使用
`external_inputs` 单独记录 fingerprint、证据路径及证据 SHA-256。

每个输入组必须同时记录：

- `manifest_path`：证据包内 `source-manifest.json` 路径。
- `manifest_json_sha256`：JSON 文件本身的完整性哈希，只用于确认文件没有被替换。
- `manifest_sha256`：由相对路径、字节长度和文件内容 SHA-256 构成的稳定文件集合指纹，
  只使用它判断输入组是否变化。

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

## 5. 分类 manifest

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File Tools/provenance/source_manifest.ps1 `
  -RepoRoot . -OutputDirectory .acceptance-<task>/<round>/manifest-production -Profile Production

powershell.exe -NoProfile -ExecutionPolicy Bypass -File Tools/provenance/source_manifest.ps1 `
  -RepoRoot . -OutputDirectory .acceptance-<task>/<round>/manifest-validation -Profile Validation

powershell.exe -NoProfile -ExecutionPolicy Bypass -File Tools/provenance/source_manifest.ps1 `
  -RepoRoot . -OutputDirectory .acceptance-<task>/<round>/manifest-governance -Profile Governance
```

Production 必须覆盖真实 GCC CMake 入口、链接配置、CI/打包脚本和生产源码。Validation
覆盖测试、runner、探针、校验工具以及两个合同模板的精确路径。不得把整个活动合同目录
纳入 profile，避免合同自引用和无关任务相互失效。Governance 覆盖 agent 规则、看板规则
和本执行合同。
当前版本化合同由矩阵 `contract_sha256` 单独绑定，避免 Governance manifest 自引用。
三类范围的唯一机器可读定义是 `Tools/provenance/manifest_profiles.json`，PowerShell
生成器和 Python 校验器必须共同读取它。Production 必须包含 GCC CMake 实际引用的
`MDK-ARM_F435/RTE/Device/-AT32F435RGT7/**` 与 `RTE/_X-Track/**`。AC5 专用
`RTE/_X-Track-App-AC5/**` 和旧 CGU7 输入不得混入 GCC Production 失效范围。

生成器与校验器枚举 Git 路径时必须使用 `git ls-files -z` 的原始字节输出，以 NUL 分隔并
严格按 UTF-8 解码。禁止使用 Git 的引号转义文本输出，否则中文等非 ASCII 路径会被漏记。
记录排序按规范化路径的 UTF-8 字节序执行。

正式 profile 使用 `etrack-input-manifest-v2`。校验器必须检查 schema、profile、字段集合、
`FileCount`、路径格式、排序、重复项、逐项长度/SHA-256、各 profile 关键入口，并按规范
重建 `source-manifest.txt`，复算内部 `ManifestSHA256` 后再与合同比较。空 manifest、伪造
内部哈希、漏掉真实 GCC/RTE 输入或缺少配套文本清单都必须失败。除此之外，最终校验必须
显式传入 `--repo-root`；校验器从该 Git worktree 重新执行 profile 枚举并读取真实文件，
要求路径集合、字节长度和内容 SHA-256 与 manifest 完全一致。仅构造一份内部自洽 JSON
或少量“关键路径”不能通过。

稳定文件集合指纹不得包含 mtime、绝对 `RepoRoot`、全局 Git `HEAD`、生成时间或证据包
保存位置。`RepoRoot` 和 `Head` 只能出现在不参与复验的 `summary.json`。因此仅触碰文件
时间、换 worktree、无关提交或移动证据目录不会触发产品复验；相对路径、字节长度或实际
文件内容改变时仍会失效。换行符变化属于实际字节变化，仍应按输入变化处理。

## 6. 自动最小复验

需要复用上一轮证据时，先生成计划。上一轮必须有可读取的精确 Git worktree；不得把当前
worktree 默认当作历史基线：

```powershell
python Tools/acceptance/validate_bundle.py `
  --contract docs/acceptance-contracts/P2-6-v2.contract.json `
  --matrix .acceptance-p2-6/<current>/evidence-matrix.json `
  --repo-root <current-worktree> `
  --previous-contract docs/acceptance-contracts/P2-6-v1.contract.json `
  --previous-matrix .acceptance-p2-6/<previous>/evidence-matrix.json `
  --previous-repo-root <previous-worktree> `
  --write-rerun-plan rerun-plan.json
```

校验器会先核对合同谱系，再比较三类 manifest 的稳定 `manifest_sha256`、external input
fingerprint、判据定义、命令定义、产物定义和上一轮判据结果，输出 `rerun_criteria`、
`reusable_criteria`、`required_commands` 和 `required_artifacts`。JSON 完整性哈希、
manifest 包内路径、绝对工作区路径或全局 `HEAD` 变化本身不得使产品判据失效。上一轮不是
`EXECUTED PASS`、稳定依赖输入变化、判据变化或执行定义变化时，该判据必须重跑。

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

最终证据包必须包含冻结合同、最终矩阵、三类 manifest、rerun plan（发生复用时）、命令
输出、决定性原始日志、最终产物和外部输入证据。所有路径必须位于矩阵所在证据包内，且
由 SHA-256 绑定。

生成 manifest、日志或计划前必须使用 worktree 输出守卫。目标文件或其任一父目录若为
symlink、junction 或其他 reparse point，必须在写入前拒绝，不能跟随链接覆盖 worktree
外或其他位置的文件。`--write-rerun-plan` 必须在创建父目录前检查一次完整父链，并在实际
写入前再次检查新建后的完整父链。

默认不保留完整构建目录、重复 checkout、源码副本和每轮重复日志。清理大文件前必须先
确认紧凑证据包能够独立解释结论。
