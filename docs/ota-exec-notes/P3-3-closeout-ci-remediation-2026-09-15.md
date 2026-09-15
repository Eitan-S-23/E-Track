# P3-3 收口治理与 CI 整改（2026-09-15）

## 范围与授权

PR #24 的已归档 v9 独立验收结果仍为 PASS，证据提交
`5695abc5d7cd1402bd0815017a3e383c57571662`、索引提交
`4df590b37c2e4f9f1f7e1aa82c47898c384164ba` 保留。
用户在收到三项建议（治理测试、CI 磁盘问题、主工作树无损保全与收口）后明确回复“授权”。
本批允许修改相关治理测试、开发 CI 配置及必要验证，并延续此前 merge commit 收口授权；
不允许改产品实现、冻结合同或 profile，不发布、部署或操作真机。

## 开工核对

两项实际 CI 阻断：

- Acceptance Governance run 34960469334：99 项测试中 1 项失败；
  `test_acceptance_bundle.py` 固定索引必须为 7 行，而当前已有 14 行，
  同一测试还把自由说明列误约束为纯 PASS，不能只把 7 改成 14。
- Flutter Development Checks run 34960338796：双宿主 analyze/test 已通过；
  Ubuntu debug APK 在 `:app:packageDebug` 和 Gradle cache 写入时
  `java.io.IOException: No space left on device`，验证/归集未执行。
  同批 release APK、Windows EXE 和自动 MCU CI 已通过，不归类为新的 OTA 产品失败。

整改先核对开发 CI 实际文件依赖与检出体积，优先减少无关检出，不删除冻结证据，
不修改生产 APK ABI 或测试范围；空间预检与日志必须能解释环境失败。
主工作树的 10 个 tracked 改动和 9 个同名未跟踪文件先与 admission 对账，
其原字节已在上批建立 SHA-256 基线，不 stash/reset 或夹带到 PR。

## 冻结边界

治理测试和开发工作流属于 Validation 输入，本批是 bundle 提交之后的独立治理/CI 变更。
旧 v9 合同、矩阵、原始证据和索引行均不改；不在新 HEAD 上把旧冻结包强行校为绿色，
也不宣称旧 PASS 自动覆盖新输入。
若未来提出新产品验收，应按现有 v3 合同和 profile 生成最小复验计划；
本批只验证治理/CI 修复及 Git 收口，不借治理变更重开历史硬件验收。

## 验证状态

本批是独立治理/CI 修复，不是新产品验收；未填新的正式验收矩阵。

### 修复与独立复核

- 索引测试去掉固定行数和纯 PASS 假设，改为校验六列结构、非空、ID 唯一、
  schema、OID 和可识别结果；保留真实 commit/tree/祖先关系核对，
  增加合同 ID 与冻结 profile blob 精确绑定，以及增长/历史结果正例和畸形行负例。
- 开发工作流使用原生 Git sparse checkout，只不物化无关固件和历史证据；
  完整 Flutter 包、测试、runner、工作流及直接文档依赖仍保留。
  APK 架构、analyze/test 范围和失败传递未改变，不删除预装工具或任何既有证据。
- Linux debug APK 在冷 SDK/Gradle 准备前记录磁盘字节并要求 12 GiB 可用空间；
  最后无条件记录 Linux 工作区磁盘使用。预算不是产品门槛，也不保证未来工具链一定够用。
- 非实现独立复核 `closeout_governance_review` 首次发现 sparse 清单及 fixture
  漏掉 `PLAN-OTA-EXEC.md` 和 `docs/acceptance-execution-contract.md`，
  它们由既有预授权测试读取。两处均已补齐，定向回归通过；复核者确认问题关闭，未留其他发现。

### 实际宿主命令

命令在 admission 工作树串行执行，Python 使用 `-X utf8 -B -S`；
测试 fixture、TEMP/TMP/TMPDIR、Git fixture 配置和日志均在项目内。

| 命令 | 实测结果 |
|---|---|
| `python -X utf8 -B -S tests/ota/test_acceptance_bundle.py` | 101 项 PASS，exit 0 |
| `python -X utf8 -B -S tests/ota/test_flutter_dev_checks.py` | 52 项 PASS，exit 0 |
| sparse/disk/standing-authorization 三项定向回归 | 补齐依赖后 3 项 PASS，exit 0 |
| `python -X utf8 -B -S tests/ota/test_flutter_dev_apk.py` | 26 项 PASS，exit 0 |
| `python -X utf8 -B -S tests/ota/test_acceptance_efficiency.py` | 32 项 PASS，exit 0 |

原始输出及退出码：admission `.cache/p3-3-closeout-20260915-01/ci-fix-*.{stdout.log,stderr.log,json}`。
真实 Actions sparse checkout、磁盘预算和 APK 产出仍待本批提交推送后验证；
没有本地 Flutter/Gradle 构建，没有重新派发 v9 合同命令或真机操作。

### 主工作树无损保全

原 10 个 tracked 改动和 9 个与 incoming tree 重名的未跟踪文件已逐字节归档，
路径为主树 `.cache/p3-3-root-preservation-20260915-01/`，
含 19 份原文件、SHA-256 清单、原 status 与 binary diff。
暂存集合精确等于这 19 份文件，原工作文件未改变；内容核对和全局提交 hook 均通过。

本地专用保全分支 `archive/p3-3-root-before-main-20260915` 的提交为
`81f93ff7d3aa3f54edc5acf7c752c498eb7a65d6`，父提交仍是原 `c89c58f`。
该分支不推送、不合并，原 `dev/flutter/apk/p3-3-t1a` 分支不改；
余下 375 份主树及 25 份 admission 既有未跟踪文件继续原位保留。
Git 可按属性规范化行尾，原始字节另由归档保证；不以 stash/reset/清理或覆盖保全数据。

### 后续门禁

修复提交只进入 admission PR #24；必要 CI 通过后才能 merge commit 合并。
主树切回 main 前再次检查 tracked clean、未跟踪/忽略文件碰撞、实际路径和完整父链，
同步后核对 `HEAD == origin/main`，并将最终 CI/合并/同步记录提交入 main。
上述步骤尚未全部完成前，P3-3 卡仍为进行中，v9 独立验收 PASS 保留原锚点。
