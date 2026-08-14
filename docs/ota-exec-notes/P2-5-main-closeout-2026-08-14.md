# P2-5 main 收口记录（2026-08-14）

## 1. 结论

P2-5 已由非实现独立验收会话正式通过，并通过 PR #2 以 merge commit 合入
`main`。P2-5 实现、R6 独立验收报告、Git/worktree 收口规则、P2-4 最终 CI
补证和本收口记录均已进入 `main`。

- 独立验收报告：
  `docs/ota-exec-notes/P2-5-F4-independent-acceptance-2026-08-10-r6.md`
- 独立验收结论：P2-5 `完成`，P2 `5/6`
- PR：<https://github.com/Eitan-S-23/E-Track/pull/2>
- PR head：`948aff596787d86668b58fbcbcb34cad8730aa7f`
- PR base：`388cb23a9de7b8ebd50304934823f8b4b2e99c4c`
- 远端 merge SHA：`309cc1e1f47f51bcaea9ce034e139e7f470013ef`
- 合并方式：merge commit；未 squash、未 rebase

## 2. 提交与冲突收口

流程规则和 P2-4 补证先于 P2-5 合并，以独立提交进入 `main`：

- `6bcbf8d` `docs(workflow): enforce worktree closeout rules`
- `388cb23` `docs(ota): record P2-4 main CI closure`

P2-5 分支的收口提交链为：

- `18f36c6`：实现修复
- `eb1d6ed`：可复现构建 provenance
- `9381c57`：R6 独立验收证据
- `948aff5`：验收后合入当时 `main` 的 merge commit

`PLAN-OTA-EXEC.md` 冲突解决同时保留了以下内容：

- P2-5 的完成状态、R6 验收证据和完整会话日志
- Git/worktree 收口规则
- 2026-08-06 流程修订日志
- P2-4 最终 `main` CI 证据

对 `p2-4-20260731` 的 `858edf8` 已逐项审计，未盲目 cherry-pick。其 `main`
尚缺的最终 CI/收口证据已由 `388cb23` 等价补入，未重复引入实现或历史噪声。

## 3. 合并前验证

绑定的 12 条宿主命令全部通过。关键逻辑回归包括：

- backup `108/108`
- confirm-health `24/24`
- SDIO timeout `9/9`
- provenance `4/4`
- patch `167/167`
- package `102/102`
- staging `48/48`
- state machine `96/96`
- vectors `9/9`

本地 GCC 首次 configure 因未提供强制的 `SOURCE_DATE_EPOCH` 而退出 1；按工作流
设置 `SOURCE_DATE_EPOCH=1786320000` 后构建通过。结果为 `634 warning / 0 error`，
另有 3 个 CMake object-path warning：

- App：`598828 B`，SHA-256
  `21CE82DD367A4A63A9F028C585475320B51DD1284A2CF7B366BCD5B7ED0E4B37`
- Boot：`14724 B`，SHA-256
  `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594`

模拟器 `/t:Rebuild` 通过，`102 warning / 0 error`；EXE 为 `5879296 B`，
SHA-256
`373B982B8A08FC12EE9D06119EAB49F9D792F5819F22FA17B57753B471CAA35E`，
结束后无残留模拟器进程。

AC5 尝试在编译前退出 1，原因是历史构建输入
`MDK-ARM_F435/Objects/X-Track.lnp` 缺失；未手写编译参数或伪造 AC5 成功。
两个 worktree 的 `git diff --check` 均通过。

## 4. 合并后 main CI

PR merge SHA `309cc1e1f47f51bcaea9ce034e139e7f470013ef` 触发的 `main` CI：

- MCU Firmware Build：run `31777803114`，`success`
- Build APK and EXE Release：run `31777803106`，`success`
- GitHub Push to WeChat Notification：run `31777803138`，`success`

MCU job `94696823695` 的原始日志统计为 `634` 条 `warning:`、`0` 条
`error:`。产物从该 run 的 artifact 下载后独立计算：

- App：`598848 B`，SHA-256
  `2DDEFC95463FC4971563C477DBB337A555E133D2B41EB8B471B8F8779E0EDF14`
- Boot：`14724 B`，SHA-256
  `3554E193F498D23210F5EF32E09DE64575B7CD39104FAFCC950740E5E8A7EC34`

条件作业结果如实保留：`Detect changed paths` 成功；Android APK、Windows EXE、
GitHub Pages、GitHub Release 和 Cloudflare firmware registration 均为 `skipped`。

## 5. main 同步与工作树保护

远端合并后已执行第一次同步闭环：

1. `git fetch --prune origin`
2. `git worktree list --porcelain`
3. 在实际检出 `main` 的 `D:\github\my\E-Track` 执行
   `git merge --ff-only origin/main`
4. 验证 `HEAD` 与 `origin/main` 均为
   `309cc1e1f47f51bcaea9ce034e139e7f470013ef`
5. `git status --short --branch` 不含 ahead/behind

两个 worktree 的既有未跟踪文件、构建噪声和 `.claude` 内容均未清理、还原、
暂存或夹带提交。CI artifact 仅下载到已授权 P2-5 worktree 的
`.cache/closeout-p2-5/post-merge-309cc1e/`，不纳入提交。

## 6. 文件系统审计

本轮主动选择的写入均位于以下两个授权根目录：

- `D:\github\my\E-Track`
- `D:\github\my\E-Track-p2-5-20260801`

前序宿主测试曾瞬时使用
`C:\Users\SU\AppData\Local\Temp\etrack-p1-1-*`；该临时目录由测试自动删除，
复核无残留。本轮后续命令已将 `TEMP`、`TMP`、`TMPDIR` 指向 P2-5 worktree 内的
`.cache/agent-temp`，未新增项目外产物。
