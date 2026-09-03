# P3-7 收口证据笔记

- 卡：P3-7 firmware-build.yml 测试步骤收敛
- 收口日期：2026-09-04（合并时刻 2026-09-03T16:15:55Z / 2026-09-04T00:15:55+08:00）
- 执行者：Claude（P3-7 非实现独立验收会话 / 收口批次），用户明确放话「先收口吧」后执行
- 本文件承载全部哈希与提交标识；看板 `PLAN-OTA-EXEC.md` 内不记任何哈希（它是
  Governance profile 的 `top_file`，写哈希会构成不收敛的自指环）

---

## 1. 收口动作时间线

| 序 | 动作 | 结果 |
|---|---|---|
| 1 | 推送 2 个收口提交至 `ota/p3-7-host-test-wiring` | `94c4d68..fcb7715` |
| 2 | PR #19 `synchronize` 触发三个工作流 | 全绿（见 §3） |
| 3 | `gh pr merge 19 --merge` | 合并提交 `40f2e8cd5a32fed1b0a745eff1322fe7964e5ced` |
| 4 | `git fetch --prune origin` | `2d8ff7e..40f2e8c main -> origin/main` |
| 5 | `git worktree list --porcelain` 定位 main | 三个 worktree 均不在 `refs/heads/main` 上（见 §4） |
| 6 | 主 worktree `git switch main` + `git merge --ff-only origin/main` | 快进 14 个提交，无冲突 |
| 7 | 核对 `HEAD == origin/main` 且无 ahead/behind | 一致（见 §4） |
| 8 | main 顶端复跑四条接线脚本 | 四条全绿（见 §5） |

---

## 2. 本卡提交清单（PR #19，13 个提交）

按 `git log --oneline 2d8ff7e..fcb7715` 时序倒排：

```
fcb7715  P3-7 第 3 轮独立验收：PASS，冻结 P3-7-v1 证据包
6e8b76b  P3-7 v2 补做与验收工具重基线
94c4d68  P3-7 反证还原(3/4, 重做)：移除 #if 0 阳性样本，预期转绿
11ca914  P3-7 反证注入(3/4, 重做)：HAL_USB.cpp 加 #if 0 反斜杠 include 阳性样本
690a528  P3-7 反证还原(4/4)：设备 model 恢复 E-Track，预期转绿
607f802  P3-7 反证注入(4/4)：设备 model 首字符改 F，预期 cmd12 变红
46c181b  P3-7 反证还原(3/4)：HAL_USB.cpp 恢复正斜杠 include，预期转绿
87a0d99  P3-7 反证注入(3/4)：HAL_USB.cpp 首行反斜杠 include（作废腿，打红了更早的 step 9）
d99c840  P3-7 反证还原(2/4)：恢复文本 sink 守卫，预期转绿
5808836  P3-7 反证注入(2/4)：移除活跃期文本 sink 守卫，预期 cmd10 变红
7b3e6c6  P3-7 反证还原(1/4)：ACK_BEGIN 恢复 10u，预期转绿
f369a5d  P3-7 反证注入(1/4)：ACK_BEGIN 长度契约漂移，预期 cmd9 变红
90facc3  P3-7 接线：firmware-build.yml 执行四条 host 回归并扩 paths 闭包
```

`87a0d99` / `46c181b` 是第 3 条反证的**作废腿**：该注错打红了更早的 CI 步骤
step 9 `Build firmware`，使目标 step 10 变成 `skipped`，反证空转，故整条作废并以
`#if 0` 包裹阳性样本重做（`11ca914` / `94c4d68`）。两腿都保留在历史中，不隐藏
失败尝试。

### 冻结资产指纹

| 资产 | 字节 | SHA-256 |
|---|---|---|
| `docs/acceptance-contracts/P3-7-v1.contract.json` | 45724 | `D26377D20F046D781931B3E276AEBC4B215EB2EAFC29929D12976491B826370C` |
| `docs/acceptance-contracts/P3-7-v1/P3-7-v1.evidence-matrix.json` | 25465 | `B3510928B1FAE49CF16282BDD9F8C12AACAD59FF60598D29817AD4FF98AFB4C4` |

三份分类 manifest 的 `ManifestSHA256`：
Production `ACAE2C71909AF7F19ADE3978E0D068525AFE513BDEDA48B8CF5D9E08711A6363`（file_count=2920）、
Validation `B5331BE603F447FE325EC99DCB54456C20D0B52585FD7ACC7918882CA47EDB60`（154）、
Governance `B35E78737A0E15E1839F48A04CC786727207CDF39211D5CAFF96DBE0908A5D96`（26）。

**可校验冻结点 = `fcb7715`（tree `26b0a97f42f1c51bfef669b6d27b765cf274fcf3`）。**
三份 manifest 记录的 `Head` 为 `94c4d68`，因为生成时看板回写与工具重基线尚在工作树中
未提交；manifest 记的是**工作树字节**，而这批工作树字节正是 `fcb7715` 提交下来的树。
故复校须 `git checkout fcb7715` 后再跑校验器。

---

## 3. 合并方式裁定：用 `merge` 而非 `squash`

**裁定：`--merge`，保留 13 个提交。**

理由：本卡的证据能力建立在**逐提交可核**之上——包内 `ci/changed-*.json` 逐条声明
「该次注错/还原提交恰含一个文件」，`ci/run-*.json` 把每次 CI 运行绑到具体 `headSha`。
squash 会把 13 个提交压成 1 个，上述声明将无法在 main 上被第三方复核，
fail-closed 反证四条腿的可信度随之塌掉。这与 P3-2（PR #16）用 merge 的理由同类。

**这条裁定的代价我不隐瞒**：与 P3-6（PR #14，用户裁定 squash）相反，本卡的
4 次注错提交现在**位于 main 的可达历史中**，`git bisect` 有可能检出一棵带注入缺陷的树
（ACK_BEGIN 长度漂移、文本 sink 守卫缺失、反斜杠 include、设备 model 首字符错）。
缓解事实三条：

1. 每次注错的**下一个提交**即为还原，缺陷树在历史中的存活跨度均为 1 个提交；
2. main 顶端树是干净的——`CMD-PRODUCT-REDLINE-DIFF` 已证分支端态相对交付基线在
   `Libraries/`、`USER/`、`boot/`、`MDK-ARM_F435/` 四个红线目录上 diff 为空，
   §5 的四条脚本复跑也在 main 顶端全绿；
3. 合并为 first-parent 线性结构，`git bisect --first-parent` 不会进入注错提交。

P3-6 与 P3-7 结论相反是因为两卡的证据结构不同：P3-6 的反证提交不承载可核声明，
排除它们纯赚；P3-7 的反证提交本身就是判据 C12 的证据载体，排除即毁证。

---

## 4. 合并前 PR 全检查绿与 worktree 闭环

推送 `fcb7715` 后 PR #19 `synchronize` 触发三个工作流，全部 `success`：

| run id | 工作流 | event | conclusion |
|---|---|---|---|
| 33770886532 | MCU Firmware Build | pull_request | success |
| 33770886557 | Acceptance Governance | pull_request | success |
| 33770886576 | Build APK and EXE Release | pull_request | success |

`Acceptance Governance` 本次被触发是因为收口批次改动了
`docs/acceptance-contracts/**` 与 `tests/ota/**`，符合验收规约「动 schema/校验器/
manifest 必须过治理 CI」的要求，其绿是本次收口的硬前置。

注：这三次运行**不进入** P3-7-v1 冻结证据集。包内 11 条腿在冻结时刻已定，
C13 的 `runs=11` / `pr_commits=11` 派生自包内冻结的 `ci/pr-19.json` 快照，
不查实时 GitHub，故 PR 后续增长到 13 个提交、第 12–14 次运行不影响任何判据。

worktree 闭环观测（`git worktree list --porcelain`）：

```
worktree D:/github/my/E-Track                  branch refs/heads/ota/p3-7-host-test-wiring
worktree D:/github/my/E-Track-p2-4-20260731    branch refs/heads/p2-4-20260731
worktree D:/github/my/E-Track-p2-5-20260801    branch refs/heads/p2-5-20260801
```

**三个 worktree 均不在 `refs/heads/main` 上**，故按规约在主 worktree
`D:/github/my/E-Track` 执行 `git switch main` 后再 `git merge --ff-only origin/main`
（切换前已核实无 tracked 改动，只有 8 个既有未跟踪文件，切换与快进均未触碰它们）。
快进 14 个提交，无冲突。核对结果：

```
HEAD        = 40f2e8cd5a32fed1b0a745eff1322fe7964e5ced
origin/main = 40f2e8cd5a32fed1b0a745eff1322fe7964e5ced
## main...origin/main            （无 ahead/behind）
```

未采用 reset 或强制覆盖。

---

## 5. main 顶端复跑四条接线脚本

```
p3_1_verify_contract_alignment    rc=0  绿
p3_1_verify_text_isolation        rc=0  绿
p3_1_verify_portability           rc=0  绿
test_ota_device_info              rc=0  绿
```

这是本卡接入 CI 的四条命令在合并后的 main 上的独立复算，证明四次注错均已彻底还原、
main 顶端不含任何注入缺陷。

---

## 6. 收口后的已知漂移（已声明，不修）

1. **本笔记与随后的看板回写会让 `P3-7-v1` 的 Governance 指纹相对 main 顶端漂移。**
   `PLAN-OTA-EXEC.md` 是 Governance 的 `top_file`，而验收结论必须写回看板——这是
   验收框架缺陷一的固有表现，不是本卡引入的问题。`P3-7-v1` 在冻结点 `fcb7715`
   上仍可完整校验。
2. **本卡改动 `.github/workflows/firmware-build.yml`（Production 的 `top_file`）
   已实查确认落在 `P3-1-v2`、`P3-2-v1`、`P3-6-v1` 三份冻结包的 Production manifest 内**
   （各命中 1 处），故这三份包在 main 顶端复校的错误条数会因本卡增加。
   按规约冻结资产禁止回改（合同 `authorized_deviations` DEV-3）。
3. **P3-6 的冻结 harness `tests/ota/p3_6_verify_ci_wiring.py` 在 main 上现为红（2 项）。**
   红因唯一且可归属：本卡按派工书授权把步骤名 `Test Boot fw_header validator vectors`
   改为与实际执行内容对齐的新名，而该 harness 把旧步骤名钉死。不回改 P3-6 冻结字节。
4. **两条触发器反证的提交不被任何 ref 指向**（临时 `master` 分支已按计划删除，DEV-6）。
   门禁复算不含任何 git 调用，只读冻结证据文件，故不受影响；受影响的仅是人工按
   SHA 追溯。

以上四条与其余遗留问题的完整清单、根因与处置建议，见
`docs/ota-exec-notes/P3-7-residual-issues.md`。

---

## 7. 索引

- 三轮验收记录：`docs/ota-exec-notes/P3-7-acceptance-round1.md` / `-round2.md` / `-round3.md`
- 审查评分（综合 94/100）：`.claude/verification-report-p3-7.md`
- 实现方证据：`docs/ota-exec-notes/P3-7-wiring-evidence.md`
- 冻结合同与证据包：`docs/acceptance-contracts/P3-7-v1.contract.json`、`docs/acceptance-contracts/P3-7-v1/`
- 遗留问题清单与交接：`docs/ota-exec-notes/P3-7-residual-issues.md`
