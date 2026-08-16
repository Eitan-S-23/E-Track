# P2-6 提示词冻结与 main 收口记录（2026-08-16）

## 1. 结论

P2-6 的**实现提示词已冻结**，冻结依据是 Acceptance Governance 的正式远端通过，
并已随 PR #3 汇入 `main`。本文件记录三轮远端证据、main 同步闭环与文件系统审计。

**本卡实现尚未开始**：`PLAN-OTA-EXEC.md` 的 P2-6 卡状态仍为 `待办`。本次收口只
交付「判据冻结 + 探针接入远端 CI」，不包含任何生产源码改动，也不含真机峰值数据。

流程位置（定向复核第二轮裁定的七步）：① 整改 ✅ → ② 提交收口并冻结实现提示词
✅（本次）→ ③ 派 Luna 实现（**下一步，待用户下令**）→ ④ 候选稳定后生成三类
manifest 并冻结 `docs/acceptance-contracts/P2-6-v1.contract.json` → ⑤ 冻结验收
提示词再派 Sol。

## 2. 提交与合并

| 提交 | 内容 |
| --- | --- |
| `68b929b` | ci(ota): P2-6 Spec 探针接入治理 CI 并修复 harness 分类（41 files, 6389+/2-） |
| `4859ec4` | docs(ota): 冻结 P2-6 实现提示词（3 files, 47+/7-） |
| `59d7755` | Merge pull request #3 from Eitan-S-23/p2-6-spec-probe-ci-20260816 |

PR：<https://github.com/Eitan-S-23/E-Track/pull/3>（`MERGEABLE` / `CLEAN`，无冲突，
merge commit 方式，与 P2-5 的 PR #2 一致）。

**为什么必须开 PR**：`acceptance-governance.yml` 的 push 分支过滤只含
`main`/`master`，只把特性分支推上去**不会**触发它（实测：仅跑了
`Build APK and EXE Release` 与微信通知）。取得正式远端结果的唯一途径是开 PR 走
`pull_request` 事件，或直接推 `main`（不可取）。

## 3. 三轮远端证据（逐项核对实际输出，不凭绿灯推定）

| 轮次 | run | head | 事件 | 探针步骤实测 | 治理回归 |
| --- | --- | --- | --- | --- | --- |
| 候选 | `31948667013` | `68b929b` | pull_request | 自检 **20/20** 逐项 PASS + 探针 **8/8 PASS**、`rc=0` | `Ran 45 tests ... OK` |
| 冻结 | `31949637644` | `4859ec4` | pull_request | 自检 **20/20** + 探针 **8/8**、结论一致 | `Ran 45 tests ... OK` |
| main | `31950044850` | `59d7755` | push | 自检 **20/20** + 探针 **8/8**、结论一致 | `Ran 45 tests ... OK` |

三轮全部 `conclusion=success`。第二轮是**冻结提交自身**的 CI —— 按裁定第 5 条，
冻结动作改动了提示词/看板/research 三处字节，不得沿用候选提交 `68b929b` 的绿灯。

远端工具链（三轮一致）：

```text
arm-none-eabi-gcc (Arm GNU Toolchain 13.3.Rel1 (Build arm-13.24)) 13.3.1 20240614
gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0
```

远端 45 项**0 跳过**；本机是「45 通过 1 跳过」，跳过项是 Windows symlink 权限所致，
在 Ubuntu 上实际执行并通过。**因此本机结果不是远端结果的上界。** 本机另行确认
`SpecProbeCiWiringTests` 6 项确实在这 45 项内。

## 4. 跨平台风险已消解（裁定第 3 条未被触发）

上一轮预先声明的风险：全部探针数值基线取自 Windows + MinGW 宿主 gcc 15.2.0，
`wrap_probe` 的 `real_pool_seq=(163,96)`、`scan4` 的 `ota_apply` 992B→520B 等精确
数值要到 Ubuntu runner 首跑才能确认。

实测结果：

1. **基线全部复现。** 探针是 fail-closed 的（记录结论冻结成期望值，结论翻转即
   非零退出），因此 `8/8 PASS` 等价于「上述数值在 Ubuntu 上同样成立」。
2. **宿主侧判据不依赖宿主 gcc 版本。** 宿主编译器跨了两个大版本
   （MinGW 15.2.0 → Ubuntu 13.3.0），`host_scan` 的 `S1..S5` 期望值不变。
   ARM 侧则仍**必须**锁 13.3.Rel1 —— 那些是逐字节基线。
3. 未触发「工具链或构型已变 → 重新裁定基线」分支，**未放宽任何判据**。

## 5. main 同步与工作树保护

合并前三个 worktree 都不在 `main` 上：

```text
D:/github/my/E-Track                 -> refs/heads/p2-6-spec-probe-ci-20260816
D:/github/my/E-Track-p2-4-20260731   -> refs/heads/p2-4-20260731
D:/github/my/E-Track-p2-5-20260801   -> refs/heads/p2-5-20260801
```

因此按收口规约第 4 条，把主 worktree（`D:/github/my/E-Track`）切回 `main` 后做
ff-only 同步，而不是只看 `origin/main` 引用：

```text
git switch main            -> behind origin/main by 3 commits, can be fast-forwarded
git merge --ff-only origin/main
HEAD        = 59d7755bf52ebf027c8846a2a7c51b75bd25b138
origin/main = 59d7755bf52ebf027c8846a2a7c51b75bd25b138   (完全一致)
git status --short --branch -> `## main...origin/main`（无 ahead/behind）
```

切换前逐个核对 4 个未跟踪文件（`.cache-cmake-time-test.cmake`、
`.claude/cc_recover_s4.js`、`.claude/ccprobe_hash.js`、`.claude/ccprobe_plan.js`）
均**不在** `origin/main` 树内，无覆盖风险；切换后全部保留。`git diff --stat HEAD`
为空，无 tracked 改动被牵连。

另两个 worktree（P2-4 / P2-5）未被触碰。

## 6. 未触发的工作流是路径隔离，不是跳过检查

`MCU Firmware Build` 在 `59d7755` 上**没有运行**。这是设计行为：本次合并改动的
路径是 `.github/workflows/acceptance-governance.yml`、`docs/**`、
`PLAN-OTA-EXEC.md`、`tests/ota/spec-probes/**`、`Tools/provenance/**`，与
`firmware-build.yml` 的路径过滤（`USER/**`、`Libraries/**`、`MDK-ARM_F435/**`、
`boot/**`、`cmake/**`、`vendor/**`、`tests/boot/**`、`tests/ota/test_ota_*.{c,py}`、
`lv_conf.h` 等）**零交集**，实测核对无命中。

这与 `69780c8` 的 `ci(governance): reject skipped GCC checks` 不冲突：那条规则针对
的是固件工作流**内部**出现 skipped 的 GCC 检查，而不是工作流因路径隔离整体不触发。
本次合并未改动任何生产源码，固件产物不受影响。

## 7. 文件系统审计

- 全部写入均在活动项目根 `D:\github\my\E-Track` 内，无项目外写入。
- 临时文件（`.cache/p2-6-commit-msg.txt`、`.cache/p2-6-pr-body.md`、
  `.cache/p2-6-freeze-msg.txt`、`.claude/plan_writeback_p2_6_round2.py`、
  `.claude/plan_writeback_p2_6_freeze.py`）用后即删，`git status` 无残留。
- `PLAN-OTA-EXEC.md` 是混排 EOL 文件（CRLF 691 + 裸 LF 89/90），两次回写都用
  Python 字节编辑并校验 CRLF 计数不变；`git diff --numstat` 分别为 `12 0` 与
  `2 1`（后者的 1 处删除是卡片行原地替换），**未发生 EOL 规范化**。
- 4 个既有无关未跟踪文件保持未跟踪，未被纳入任何提交。

## 8. 下一步的前置条件

派 Luna 之前无遗留阻断。派单后需注意：

- 提示词已冻结为**只读判据源**。Luna 发现判据矛盾或不可实现 → 把 P2-6 置「阻塞」+
  在看板 §9 变更登记表登记，**不得就地改判据继续实现**。改判据必须重新走
  「整改 → 远端 CI 通过 → 再冻结」。
- `docs/acceptance-contracts/P2-6-v1.contract.json` 按裁定第 7 条**等实现候选稳定
  后**再创建，不得提前生成。
- Luna 不执行 `git commit/push/merge`；实现者不自验收。
