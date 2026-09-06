# P3-3 派单就绪状态修正

日期：2026-09-07。范围：派单治理，不认领或实现 P3-3 产品代码。

## 核对依据

- 当前根目录为 `D:/github/my/E-Track`，基线为 main
  `7c9a0f725516fadfd1bf2a5daef5c02acaa6f2ef`。
- `PLAN-OTA-EXEC.md` 的 P3-1、P3-2 均已完成独立验收并收口至 main；
  P3-1 见 PR #12/#13，P3-2 见 PR #16。不重跑历史轮次核验器。
- P3-3 的实施 Spec 已存在且只引用看板中的派单状态；共享合同已冻结。
- 首次状态修正仅获准更新派单状态和提供实现提示词，当时未获准提交推送。
  后续提交授权与遗留文件处置见下文；部署和硬件操作仍不在授权内。

## 集中检查与处置

| ID | 发现与依据 | 处置与范围 |
|---|---|---|
| R1 | readiness 仍因已完成的 P3-1/P3-2 阻塞 P3-3；测试同时钉死旧可派单集合 | 同步修正看板摘要、P3-3 行及精确集合断言，保留等值检查；登记 §9/§10 |
| R2 | P3-3 卡要求 APK 可装、真机 toy/真包传输；实施 Spec 的末条完成判据却把真机安装和传输留给 P3-5 | 本次不迁移或删减验收门槛。派单解锁实施，不代表完成；正式验收冻结前由非实现方集中确认归属，未观测的真机项不得记 PASS |

P3-3 保持待办、未认领，P3 阶段仍为 4/7。本次仅修正派单资格，不新增 P4-2
作为 P3-3 的实施前置。P3-4 最终生产参数、P4-2 真实服务和 P3-5 全链路要求
仍须分别落实；fake/fixture 测试不得冒充真实手机、云端或 MCU 观测。
不修改共享合同、现有实施 Spec、历史冻结包或其他任务的依赖。

## 验证计划

先更新期望集合，在旧看板上运行单条派单测试，确认其能拒绝过期状态；再修正
看板并运行 `PostP26SpecGovernanceTests`。使用 `python -X utf8 -B`，
所有日志与临时目录限定于 `.cache/p3-3-readiness/`，不启动 PowerShell。
最终检查 `git diff --check`，并复核未修改产品、冻结资产或既有未跟踪文件。

本地自测、治理 CI、独立验收和 Git 收口分别记录，不能互相替代。

## 本地验证结果

1. `python -X utf8 -B tests/ota/test_acceptance_bundle.py PostP26SpecGovernanceTests.test_readiness_matrix_mirrors_board_order_and_derives_dispatch -v`
   在旧看板上 exit 1，唯一失败为可派单集合缺少 P3-3，证明断言未被放宽。
2. `python -X utf8 -B tests/ota/test_acceptance_bundle.py PostP26SpecGovernanceTests -v`
   在修正看板后 exit 0，18/18 通过，无 skipped。

本地原始输出：

| 文件 | SHA-256 |
|---|---|
| `.cache/p3-3-readiness/before.log` | `0a1e1b23d6a2827613aba173dfa66f41a1e529fe826e487ac377e78bc95d2b32` |
| `.cache/p3-3-readiness/after.log` | `406448b1696321cda4753bf7f99a8e53868334d4d8e0099703751a2563399130` |

首次本地验证结束时尚未执行治理 CI、正式独立验收或提交推送；本地结果不冒充这些结论。
未触发 Flutter/固件构建、云端部署或硬件动作。

## 授权提交与遗留文件核查

用户随后明确要求提交推送，避免其他实现/验收会话读取旧派单状态。本批只提交
`PLAN-OTA-EXEC.md`、`tests/ota/test_acceptance_bundle.py` 和本记录，使用
`Eitan-S-23` 身份普通推送 main，不强推、不改写历史。提交前已核对远端 main
仍等于上述基线且没有分支保护要求；提交后的 CI 结果须按实际 commit 查询
`Acceptance Governance`，不得拿此前提交的绿灯替代。本轮不属于 P3-3 产品独立验收。

此前所说的 8 个未跟踪文件均为历史临时工具，不是漏交的 P3-3 产品实现：

| 文件 | 实际用途 | 是否原样入库 |
|---|---|---|
| `.cache-cmake-time-test.cmake` | 输出 CMake UTC 时间格式的独立小实验 | 否，不参与构建 |
| `.claude/ccprobe_hash.js`、`.claude/ccprobe_plan.js` | 读取本机 cc-connect/Claude 会话目录，排查分片和恢复前置 | 否，依赖本机私有会话数据 |
| `.claude/cc_recover_s4.js` | 指定历史会话的恢复脚本，含本机会话/用户标识，执行会写用户目录 | 否，不宜发布且不属于验收工具 |
| `.claude/write_p3_2_acceptance_board.py`、`.claude/write_p3_7_acceptance_board.py` | 将当轮固定结论回写看板，仍携带看板属于旧 Governance manifest 的过期假设 | 否，不是可复用核验器 |
| `.claude/write_r5_phase0_board.py`、`.claude/write_r5_ruling_board.py` | 固定 P2-6 R5 文本、路径和位置的一次性看板回写 | 否，不能用于当前卡 |

另发现 `.P3-5` 为 0 字节空文件，进入本轮时已经存在；没有项目功能或证据用途，
也不纳入提交。当前因此保留 9 个既有未跟踪文件，而非原先的 8 个。

对这些文件只做静态读取、引用检索和 SHA-256 核对，未执行、修改、删除或隐藏。
已跟踪引用出现在历史排除清单、报告和轮次范围核验器中，不是当前产品/CI 的执行入口；
当前 profile 配置也未将这些路径纳入验收输入。保留未跟踪不是为了让旧核验器在 HEAD
复绿，也不许可未来把它们作为隐式 harness。若未来确需复用某项功能，应另行去除私有
数据和硬编码环境、明确输出边界并正式纳入受管工具及其测试，不能直接调用遗留脚本。
