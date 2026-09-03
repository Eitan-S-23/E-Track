# P3-7 firmware-build.yml 测试步骤收敛实施 Spec

task_id: P3-7

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-7` 行。本文件不得另行维护该状态。

## 目标

把 P3-6 遗留的三条**产品回归**接入 `.github/workflows/firmware-build.yml` 的 host 测试执行步骤，并在同一批次内扩 `paths` 触发器使这些脚本自身的改动能触发该 workflow，同时把该步骤的名称与其实际执行内容对齐。三件事必须同批完成：只接执行而不扩触发器，等于把门禁改成「改它自己不触发它自己」的静默缺口，正是本卡要消除的东西。

## 非目标

- 不修改 `Libraries/OTA/**` 的任何产品实现，也不修改被接入脚本的判据、校验点计数或输出标记。
- 不接入 `p3_1_verify_artifacts.py`、`p3_1_verify_command_fidelity.py`、`p3_1_verify_production_binary.py`、`p3_1_verify_rx_ring_budget.py`、`p3_1_verify_mutation.py`；这五条的归类已在 `docs/ota-exec-notes/P3-7-card-creation.md` §3、§4 闭合定案，本卡不重开该裁定。
- 不改动 workflow 的构建矩阵、缓存、工具链版本、构建目标或产物上传逻辑。
- 不新增第二条 workflow，不引入 `pytest`/`tox` 等新运行器，不改变现有 host 测试的自运行入口约定。
- 不回改 P3-1 或 P3-6 的验收合同、证据矩阵、证据笔记历史观测值，也不回改 P3-6 卡内已验收的分类裁定文本。

## 前置依赖

- P3-1、P3-6 均已收口合并入 main：三条待接脚本与两套 BLE host 测试都已是 main 上的跟踪文件，先接线必红的前提不存在。
- `docs/ota-exec-notes/P3-7-card-creation.md` 记录了逐脚本实跑的退出码、耗时与耦合来源，是本卡分类结论的取证基线。
- 本卡须自带新 `task_id` 的独立验收合同，按 `docs/acceptance-execution-contract.md` 冻结后再验收；验收由非实现会话执行。

## 权威合同

- `OTA-XC-BLE-LIFECYCLE`
- `docs/acceptance-execution-contract.md`（独立验收执行规约）
- `AGENTS.md`「OTA 执行规约」与「GCC / Linux CI 源码可移植防坑」
- `docs/ota-exec-notes/P3-7-card-creation.md` §3 至 §6（分类裁定与红线来源）

## 现有组件和代码入口

- `.github/workflows/firmware-build.yml`：`push` 与 `pull_request` 各有一份 `paths` 列表，当前用 `tests/ota/test_ota_*.c`、`tests/ota/test_ota_*.py` 覆盖 OTA host 测试；`Test Boot fw_header validator vectors` 是唯一 host 测试执行步骤，在 `set -euo pipefail` 下已执行 8 条命令，但步骤名只提及 fw_header。
- `tests/ota/p3_1_verify_contract_alignment.py`：静态比对源码与冻结二进制合同，成功时打印含零漂移计数的单行标记。
- `tests/ota/p3_1_verify_text_isolation.py`：以子进程方式驱动同仓会话测试，验证明文零泄漏与 sink 守卫。
- `tests/ota/p3_1_verify_portability.py`：扫描 `Libraries`、`USER`、`MDK-ARM_F435/Platform` 的反斜杠 `#include`，靠 `.old` 存档提供阳性对照，对照为空即判失败。
- `Tools/provenance/manifest_profiles.json`：`.github/workflows/firmware-build.yml` 在 Production profile 内是 `top_file` 兼 `required_path`。

## 输入输出与调用方向

- 输入：仓库源码树与 Ubuntu runner 上的 `python3`；三条脚本均不依赖构建产物、不依赖本机绝对工具链路径，可在构建步骤之前或之后执行。
- 输出：CI 日志中三条脚本的实际执行输出与各自单行结论标记，以及任一非零退出使整个 job 变红的能力。
- 调用方向单一：workflow 步骤 -> `python3 tests/ota/p3_1_verify_*.py`。脚本不得反向依赖 workflow 环境变量、runner 专有路径或 `GITHUB_*` 变量。
- 触发器与执行必须构成闭包：**每一条被写入执行行的脚本路径，都必须至少被 `push` 与 `pull_request` 两份 `paths` 列表中的一条模式覆盖**，两份列表内容必须保持同步。

## 状态机与生命周期所有者

- workflow 步骤拥有一次 CI 执行的生命周期；三条脚本各自拥有其临时产物，不得把中间产物留在仓库跟踪路径下。
- 产品状态机仍由 `Libraries/OTA/**` 拥有，本卡不介入，只保证其回归被执行。
- 分类裁定的所有者是 `docs/ota-exec-notes/P3-7-card-creation.md`：一旦本卡通过独立验收，未接入的五条脚本不得在无 §9 登记的情况下被反向改判。

## 错误、超时、重试、取消、恢复与幂等

- 任一被接入脚本非零退出即判失败，整个 job 变红；禁止重试掩盖偶发失败，出现不稳定必须定位为产品或脚本缺陷再处置。
- 三条脚本必须可重复执行且幂等：同一 checkout 连续两次运行结论一致，不依赖上一轮残留。
- runner 缺 `python3`、缺宿主编译器等环境问题按 `ENV_BLOCKED` 处置并如实登记，不得改判为通过。
- 取消 CI 运行不产生持久化副作用；本卡不写任何设备状态、缓存或远端资源。
- fail-closed 反证必须可完整还原：注入缺陷 -> 观测变红 -> 还原 -> 观测转绿，三步都留证。

## 允许修改范围

- `.github/workflows/firmware-build.yml`：仅限既有 host 测试步骤内追加执行行、该步骤的 `name` 字段、以及 `push`/`pull_request` 两份 `paths` 列表的条目增补。
- `docs/ota-exec-notes/P3-7-*.md`：接线记录、CI 运行记录与 fail-closed 反证证据。
- `docs/acceptance-contracts/`：本卡自身的新 `task_id` 验收合同与证据矩阵。
- `PLAN-OTA-EXEC.md`：仅本卡的状态、认领、更新与证据字段，以及 §10 会话日志行。

## 禁止修改与生产红线

- **禁止重命名或移动 `tests/ota/p3_1_verify_*.py`**。改名成能被现有 `tests/ota/test_ota_*.py` 模式匹配看似省事，但这 8 个路径被 `P3-1-v2` 与 `P3-6-v1` 两份冻结合同的 Validation manifest 逐路径绑定，改名会把哈希漂移升级为文件缺失，两份合同无法再按路径复算。必须扩触发器，不许改文件名。
- **禁止删除或改动 `Libraries/USB_MSC/msc_diskio.c.old`**。它是可移植性扫描的唯一阳性对照来源，删掉后该脚本按设计直接判失败。
- **禁止修改 workflow 顶层 `name:` 与 `jobs.build.name`**（`Build firmware (arm-none-eabi-gcc)`）。分支必需检查按「workflow 名 / job 名」标识；改步骤名是纯展示层且安全，改这两个会打断必需检查。
- 禁止修改 `Libraries/OTA/**`、`boot/**`、`USER/**` 的产品源码来「让脚本变绿」。
- 禁止用 `|| true`、`continue-on-error: true`、`if: always()`、`set +e`、`|| :`、`exit 0` 等任何方式削弱 fail-closed 语义，也禁止把执行挪出 `set -euo pipefail` 保护或改为仅在特定分支执行。
- 禁止用「本地执行通过」或「workflow 文本 diff」替代真实 CI 运行日志。

## 必须新增或调整的测试

- 三条脚本本身不新增判据；本卡的「测试」是对接线与触发器闭包的验证：
  - 正例：特性分支推送后，CI 日志出现三条脚本的实际执行输出与各自结论标记，且 job 为绿。
  - 触发器反证：提交一次**只改动被接入脚本文件本身**的推送，确认该 workflow 被触发并执行到这些脚本。若不触发，即说明 `paths` 闭包未成立，本卡未完成。
  - fail-closed 反证：对三条脚本各自注入一次可定界缺陷（分别落在合同对齐、文本隔离、可移植性三条判据上），确认 workflow 变红且红在对应那一行，随后还原并确认转绿。仅给正例不算完成。

## 完成判据

- workflow 的 host 测试步骤显式执行三条脚本，且步骤 `name` 已能涵盖其实际执行内容（boot 向量、OTA host 测试与 P3-1 产品回归）。
- `push` 与 `pull_request` 两份 `paths` 列表都覆盖三条被接入脚本的路径，且两份内容一致。
- 至少一次真实 CI 运行日志显示三条脚本的实际执行输出与结论标记，计数与 `docs/ota-exec-notes/P3-7-card-creation.md` §3 的本机基线一致。
- 触发器反证与三次 fail-closed 反证完整，run 标识、提交 SHA 与关键日志片段均已留证。
- `python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle` 全绿，`.github/workflows/acceptance-governance.yml` 通过。
- 本卡独立验收合同已冻结并通过 `python Tools/acceptance/validate_bundle.py` 校验。

## 停止条件

- 若三条脚本在 Ubuntu runner 上因源码可移植性、编码或路径问题无法运行，先按 `AGENTS.md` 相应章节定位；若需修改产品源码或修改脚本判据才能通过，置本卡为阻塞并在看板 §9 登记，不得就地改产品实现或改判据继续。
- 若发现扩触发器会与其他在途卡的冻结指纹产生无法分离的冲突，停止并登记，不得回改他卡合同。
- 若 CI 出现无法定界的偶发失败，连续三次未能定位即停止复盘，不得靠重试或放宽退出码收敛。

## 后续证据

证据落 `docs/ota-exec-notes/P3-7-*.md`：workflow diff 摘要、触发器反证与三次 fail-closed 反证的 run 标识与提交 SHA、CI 日志中三行结论标记的原文、注入缺陷与还原的具体内容。合同、证据矩阵与产物哈希登记在证据笔记与 `docs/acceptance-contracts/`，看板只记路径与结论、不记任何哈希。

## Luna 可自行决定

执行行在步骤内的排列顺序、步骤名的具体措辞、`paths` 条目用通配模式还是逐个文件名列举（只要满足闭包要求且两份列表同步）、证据笔记的分文件切分方式，以及三处注入缺陷的具体选点（只要各自能被对应脚本确定性捕获且可完整还原）。

## 阻断性决策

- 无。本卡不依赖任何未决决定；执行要求以「权威合同」章节引用的冻结条款、规约与红线为准。
