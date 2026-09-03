# P3-7 检索与接线设计（编码前落盘）

- 会话: Claude(P3-7 实现 agent, P3-7-WIRING-20260903)
- 日期: 2026-09-03
- 基线提交: `2d8ff7e52d4c575a4d109b1477a79a7c1493d81b`（main，PR #18 合并后）
- 派工书: `docs/ota-prompts/prompt-P3-7-implementation.md`（权威）
- 认领: 已在看板 §6 P3-7 卡置「进行中」并写认领标识（Python 字节编辑，diff 仅 1 行）

## 1. 相似实现分析（既有 3 例）

1. **P3-6 接线**（PR #14，看板 P3-6 卡）：在同一 workflow 同一步骤内追加
   `test_ota_ble_frame.py` / `test_ota_ble_session.py` 两行执行，无新增步骤、
   无修改 `set -euo pipefail` 块结构。本卡沿用同一模式：在既有步骤 `run:` 块
   尾部追加三行 `python3` 执行行。
2. **既有 host 测试步骤**（`firmware-build.yml:186-197`）：8 条命令线性排列于
   一个 `set -euo pipefail` 块中，任一非零退出使 job 变红。追加的三行进入同
   一保护域，不在其外。
3. **既有 `paths` 触发器模式**（同文件 push/pull_request 两份列表）：逐模式
   列举（如 `tests/ota/test_sdio_command_timeouts.py` 单文件成条）。本卡按此
   先例，对三条脚本用单文件精确条目逐个列举，而不用宽泛通配（闭包可核对性
   优先；派工书 §「Luna 可自行决定」明确允许逐个文件名列举）。

## 2. 现状与目标

- 现状：host 测试步骤名 `Test Boot fw_header validator vectors`，实际执行
  3 条 boot 测试 + 5 条 OTA host 测试共 8 条命令；三条 `p3_1_verify_*.py`
  产品回归不在任何 CI 执行路径上，其文件路径也不匹配两份 `paths` 列表中任何
  模式（`tests/ota/test_ota_*.py` 不匹配 `p3_1_verify_*` 前缀）。
- 目标（三件事同批，缺一即未完成）：
  1. 步骤内追加 3 行执行行；
  2. `push` 与 `pull_request` 两份 `paths` 各追加 3 个条目，两份同步；
  3. 步骤 `name` 改为涵盖 boot 向量、OTA host 测试与 P3-1 产品回归。

## 3. 本地基线（2026-09-03 实测，本机 main @ 2d8ff7e）

| 脚本 | 退出码 | 结论标记 |
|---|---:|---|
| `p3_1_verify_contract_alignment.py` | 0 | `P3_1_CONTRACT_ALIGNMENT=PASS drift=0 checks=47` |
| `p3_1_verify_text_isolation.py` | 0 | `P3_1_TEXT_ISOLATION=PASS cases=3 transparent=0 trace_points=1 sink_guard=True` |
| `p3_1_verify_portability.py` | 0 | `P3_1_PORTABILITY=PASS scanned=895 control_hits=1 live_hits=0 new_src_hits=0` |

与 `P3-7-card-creation.md` §3 基线一致（scanned 计数 893→895 为目录自然
增长，属非判据字段）。治理基线：`python -X utf8 -B -m unittest
tests.ota.test_acceptance_bundle` 65/65 OK。

## 4. 设计决策

- **执行行位置**：追加在既有 8 条命令之后（步骤尾部）。三条脚本只读源码树，
  不依赖构建产物（派工书「输入输出与调用方向」确认），先后皆可；放尾部使
  既有测试日志结构不变，diff 最小。
- **`paths` 条目形式**：三个单文件精确条目
  `tests/ota/p3_1_verify_contract_alignment.py` 等，两份列表同序追加。
  不用 `tests/ota/p3_1_verify_*.py` 通配：该模式会同时覆盖**不接入**的另外
  5 个脚本（mutation/production_binary/rx_ring_budget/artifacts/
  command_fidelity），使改动「验收工具」也能触发全量固件构建，超出本卡闭包
  要求（闭包要求是「每一条执行行至少被一份列表的一条模式覆盖」，反之不要求
  覆盖未接入脚本）。精确列举让触发范围与执行范围严格互镜。
- **步骤名**：`Run host tests (boot vectors, OTA host tests, P3-1 product
  regressions)`。只改步骤 `name`，不动顶层 `name: MCU Firmware Build` 与
  `jobs.build.name`（红线）。
- **不改脚本**：三条脚本本体零改动（P3-1-v2 / P3-6-v1 冻结 Validation
  manifest 逐路径绑定）。
- **fail-closed 语义**：三行裸 `python3 ...` 直接置于 `set -euo pipefail`
  块内，无 `|| true` / `continue-on-error` / `if: always()` / 条件执行。

## 5. CI 证据方案（交付要求：正例 + 1 次触发器反证 + 3 次 fail-closed 反证）

按 §0 规约 8，本会话不执行 `git commit/push`。CI 证据需要主会话推送后由
本会话或后续会话从 Actions 拉取日志。方案：

- **正例**：特性分支推送接线 commit，run 绿，日志含三条结论标记原文。
- **触发器反证**：再推一次只改被接入脚本自身的 commit（对
  `p3_1_verify_portability.py` 追加一行注释），确认 workflow 被触发且执行
  到该脚本。
- **三次 fail-closed 反证**（各一次注入→红在对应行→还原→转绿）：
  1. 合同对齐：临时把 `Libraries/OTA/ota_ble_frame.h` 某常量改漂
         （产品源临时注错，还原后恢复字节）→
         `p3_1_verify_contract_alignment.py` 行红。
  2. 文本隔离：临时把 `USER/HAL/HAL_Bluetooth.cpp` 的 sink 守卫改掉 →
         `p3_1_verify_text_isolation.py` 行红。
  3. 可移植性：在手写源（如 `Libraries/OTA/ota_ble_frame.h` 临时 include
         一条反斜杠路径）注入反斜杠 `#include` →
         `p3_1_verify_portability.py` 行红。
  注错均在特性分支临时提交，绝不进入 main；还原后必须字节级恢复
  （`git checkout -- <file>` 后用 `git diff` 确认零差异）。

注：注入对象是**产品源码**而非脚本判据，可被对应脚本确定性捕获；派工书
「Luna 可自行决定」允许选点，仅要求可定界、可还原。

## 6. 风险与停止条件

- 改 workflow 会使 P3-1-v2 / P3-6-v1 的 Production top_file 指纹漂移——派工书
  已声明属预期状态，本卡自带新 task_id 合同，不回改他卡。
- 三条脚本在 Ubuntu runner 上的运行环境仅依赖 `python3`（runner 自带）与
  源码树；`text_isolation` 子进程调用 `sys.executable`，CI 上即 `python3`。
  无 ENV 风险预判；若实跑出现环境缺失按 `ENV_BLOCKED` 登记而非改判。
- 治理测试 `test_acceptance_bundle.py` 不钉死本卡 paths 内容，但收口前必须
  全绿（派工书完成判据）。
