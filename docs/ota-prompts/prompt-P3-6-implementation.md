# P3-6 BLE 帧层测试 CI 接线实施 Spec

task_id: P3-6

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-6` 行。本文件不得另行维护该状态。

## 目标

把 P3-1 已合入 main 的两套 BLE host 测试接入 `.github/workflows/firmware-build.yml` 的测试执行步骤，使帧层与会话层回归在每次触发上真实执行，并证明该接线具备 fail-closed 能力（引入缺陷时 workflow 必须变红）。动手前必须先在本卡内裁定 P3-1 新增的 `tests/ota/p3_1_verify_*.py` 属「验收工具」还是「产品回归」，据此决定是否一并接线；不得默认全接。

## 非目标

- 不修改 `Libraries/OTA/ota_ble_*.{c,h}` 的产品实现，也不修改两套测试的断言内容或校验点计数。
- 不改动 workflow 的触发器、矩阵、缓存、工具链版本或构建目标；`paths` 触发器已含 `tests/ota/test_ota_*.c` 与 `tests/ota/test_ota_*.py`，本卡只补执行。
- 不新增第二条 workflow、不引入 `pytest`/`tox` 等新测试运行器，不改变现有 host 测试的自运行入口约定。
- 不回改 P3-1 的验收合同、证据矩阵或已冻结的 manifest 指纹。
- 不把 P3-1 的验收专用校验脚本无差别塞进生产回归，除非本卡已给出书面归类理由。

## 前置依赖

- P3-1 已收口并合入 main：`Libraries/OTA/ota_ble_{ring,frame,session}.{c,h}` 与 `tests/ota/test_ota_ble_frame.py`、`tests/ota/test_ota_ble_session.py` 已是 main 上的跟踪文件。接线前须先确认这一点，否则 CI 必红。
- `docs/ota-exec-notes/P3-1-build-evidence.md` 与 `docs/ota-exec-notes/P3-1-acceptance-verification.md` 记录了两套测试的本地执行基线（校验点计数），可作为 CI 输出的比对锚。
- 本卡须自带新 `task_id` 的独立验收合同，按 `docs/acceptance-execution-contract.md` 冻结后再验收。

## 权威合同

- `OTA-XC-BLE-LIFECYCLE`
- `docs/acceptance-execution-contract.md`（独立验收执行规约）
- `AGENTS.md`「OTA 执行规约」与「GCC / Linux CI 源码可移植防坑」

## 现有组件和代码入口

- `.github/workflows/firmware-build.yml`：`Test Boot fw_header validator vectors` 步骤是唯一 host 测试执行点，当前显式执行 `tests/boot/test_fw_header_vectors.py`、`tests/boot/test_boot_protocols.py`、`tests/boot/test_boot_state_machine.py`、`tests/ota/test_ota_staging.py`、`tests/ota/test_ota_package.py`、`tests/ota/test_ota_patch.py`。
- `tests/ota/test_ota_ble_frame.py`、`tests/ota/test_ota_ble_session.py`：P3-1 交付的两套 host 测试，各自编译并驱动同名 `.c` harness，成功时打印带校验点计数的单行结论。
- `tests/ota/p3_1_verify_*.py`：P3-1 的独立验收校验脚本（产物、命令保真、合同对齐、变异、可移植性、生产二进制、RX 环预算、文本隔离），归类结论由本卡给出。
- `Tools/provenance/manifest_profiles.json`：`.github/workflows/firmware-build.yml` 在 Production profile 内是 `top_file` 兼 `required_path`。

## 输入输出与调用方向

- 输入：仓库源码树（含 `Libraries/OTA/ota_ble_*.c` 与 `tests/ota/test_ota_ble_*.{c,py}`）与 Ubuntu runner 上的 `python3` + 宿主 C 编译器。
- 输出：CI 运行日志中两套测试的实际执行行，以及非零退出时使整个 job 变红的能力。
- 调用方向单一：workflow 步骤 -> `python3 tests/ota/test_ota_ble_*.py` -> 各自编译并运行 host harness。测试不得反向依赖 workflow 环境变量或 runner 专有路径。
- 步骤已在 `set -euo pipefail` 下运行，单个测试非零退出必须立即终止该步骤，不得用 `|| true`、`continue-on-error` 或汇总变量吞掉失败。

## 状态机与生命周期所有者

- workflow 步骤拥有一次 CI 执行的生命周期；两套 host 测试各自拥有自身临时构建产物的创建与清理，不得把中间产物留在仓库跟踪路径下。
- 产品状态机（BLE 会话与帧层）仍由 `Libraries/OTA/ota_ble_session.c` 拥有；本卡不介入其状态迁移，只保证其回归被执行。
- 归类裁定（验收工具 / 产品回归）的所有者是本卡：一旦写入本卡证据笔记并被独立验收确认，后续任务不得在无登记的情况下反向改判。

## 错误、超时、重试、取消、恢复与幂等

- 任一被接线测试非零退出即判失败，整个 job 变红；禁止重试掩盖偶发失败，若出现不稳定必须定位为产品或 harness 缺陷再处置。
- 测试必须可重复执行且幂等：同一 checkout 连续两次运行结果一致，不依赖上一轮残留产物。
- 编译器缺失、Python 版本不符等环境问题按 `ENV_BLOCKED` 处置并如实登记，不得改判为通过。
- 取消 CI 运行不产生持久化副作用；本卡不写任何设备状态、缓存或远端资源。
- fail-closed 反证提交必须可完整还原：注入缺陷 -> 观测变红 -> 还原 -> 观测转绿，三步都留证。

## 允许修改范围

- `.github/workflows/firmware-build.yml`：仅在既有测试执行步骤内追加执行行。
- `docs/ota-exec-notes/P3-6-*.md`：归类裁定、CI 运行记录与 fail-closed 反证证据。
- `docs/acceptance-contracts/`：本卡自身的新 `task_id` 验收合同与证据矩阵。
- `PLAN-OTA-EXEC.md`：仅本卡的状态、认领、更新与证据字段，以及 §10 会话日志行。

## 禁止修改与生产红线

- 禁止修改 `Libraries/OTA/**` 的任何产品源码来「让测试变绿」。
- 禁止修改两套 BLE 测试的断言、校验点计数或输出标记；接线不是重写测试。
- 禁止回改 P3-1 的验收合同、证据矩阵或其证据笔记中的历史观测值。
- 禁止在 workflow 中用 `|| true`、`continue-on-error: true`、`if: always()` 或忽略退出码的汇总语句削弱 fail-closed 语义。
- 禁止把测试执行挪出 `set -euo pipefail` 保护的步骤，或改为仅在特定分支执行。
- 禁止用「本地执行通过」或「workflow 文本 diff」替代真实 CI 运行日志。

## 必须新增或调整的测试

- 两套 BLE host 测试本身不新增断言；本卡的「测试」是对接线本身的验证：
  - 正例：在特性分支推送后，CI 日志中出现两套测试的实际执行输出（含 `P3_1_BLE_FRAME=PASS checks=39` 与 `P3_1_BLE_SESSION=PASS checks=105` 两行标记），且 job 为绿。
  - 负例（fail-closed 反证）：在特性分支上临时注入一处可定界缺陷（例如改动 `Libraries/OTA/ota_ble_frame.c` 中一处边界判断），推送后确认 workflow 变红且红在被接线的那一行，随后还原并确认恢复为绿。
- 若裁定把某个 `p3_1_verify_*.py` 归入产品回归并一并接线，必须为其补一次同样的正例/负例双向证明，不得只给正例。

## 完成判据

- `.github/workflows/firmware-build.yml` 的测试步骤显式执行 `python3 tests/ota/test_ota_ble_frame.py` 与 `python3 tests/ota/test_ota_ble_session.py`。
- 至少一次真实 CI 运行日志显示两套测试的实际执行输出与两行标记，校验点计数与 P3-1 本地基线一致。
- fail-closed 反证完整：注入缺陷的运行变红、还原后的运行转绿，两次运行的 URL 或 run id、提交 SHA 与关键日志片段均已留证。
- `tests/ota/p3_1_verify_*.py` 的归类裁定已写入证据笔记，并说明未接线者的理由与后续处置。
- 本卡的独立验收合同已冻结并通过 `python Tools/acceptance/validate_bundle.py` 校验；验收由非实现会话执行。

## 停止条件

- 若发现两套 BLE 测试在 Ubuntu runner 上因源码可移植性问题（反斜杠 include、路径过长等）无法运行，先按 `AGENTS.md` 相应章节定位；若需修改产品源码才能通过，置本卡为阻塞并在看板 §9 登记，不得就地改产品实现继续。
- 若接线后 CI 稳定性出现无法定界的偶发失败，连续三次未能定位即停止并复盘，不得靠重试或放宽退出码收敛。
- 若发现修改 `.github/workflows/firmware-build.yml` 会与其他在途卡的冻结指纹产生无法分离的冲突，停止并登记，不得回改他卡合同。

## 后续证据

证据落 `docs/ota-exec-notes/P3-6-*.md`：workflow diff 摘要、两次 CI 运行（红/绿）的 run 标识与提交 SHA、日志中两行标记的原文、注入缺陷与还原的具体内容、`p3_1_verify_*.py` 归类裁定与理由。合同、证据矩阵与产物哈希登记在证据笔记与 `docs/acceptance-contracts/`，看板只记路径与结论、不记任何哈希。

## Luna 可自行决定

执行行在步骤内的排列顺序、是否为两套测试补一行注释说明其来源、证据笔记的分文件切分方式，以及注入缺陷的具体选点（只要该缺陷可被两套测试之一确定性捕获且可完整还原）。

## 阻断性决策

- 无。本卡不依赖任何未决决定；执行要求以「权威合同」章节引用的冻结条款与规约为准。
