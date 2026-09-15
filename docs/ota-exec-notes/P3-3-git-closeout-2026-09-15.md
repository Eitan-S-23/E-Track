# P3-3 Git 收口记录（2026-09-15）

## 当前状态

P3-3-v9 独立验收五项全部 PASS，结论采用
`docs/ota-exec-notes/P3-3-v9-acceptance-2026-09-15.md`。
主会话只办理 Git 收口，不参与重新实现或重新判定验收。
PR #24 已在必要 CI 全绿后用 merge commit 合并，主工作树已安全同步到 main，
最终证据和操作事实见本文末节。看板置“完成”，实现认领 Claude(P3-3-IMPL-20260907) 不变。
本记录初次提交时的未完成状态及其后失败/修复过程保留在以下历史章节，
不使用旧状态覆盖当前 v9 PASS，也不让旧 PASS 冒充后续治理输入的验收。

## 归档身份

- 分支：`dev/flutter/apk/p3-3-admission`，仓库 `Eitan-S-23/E-Track`。
- GitHub 操作身份已核对为 `Eitan-S-23`。
- freeze_commit：`ceaf8d2b7bb8e78968462af51a57ff1250731b61`。
- freeze_tree：`4fd600a48a25654fe82db3cb6fd6f6338392bc48`。
- profile_config_blob：`3769369d053aad028b67d7e2c17b5827b2b96f55`。
- 证据 bundle_commit：`5695abc5d7cd1402bd0815017a3e383c57571662`。
- v9 合同 SHA-256：`8b0fd07a8e01070d2eda5745ea73ec0e6759911c45796c3289dadce54a44950f`。
- v9 终态矩阵 SHA-256：`26ea1e0d9fa54da3837bdfcbe551e9fdf07b621a4b03f10ef326bd4aff8264c2`。

证据提交包含必要 v7 历史、完整 v8 来源包、完整 v9 当前包和四份对应报告；
367 个文件全部完成交付字节与暂存 blob 的 SHA-256 核对，362 个文件产生提交差异。
v8 R1 四项原始 EXECUTED PASS 随包保留，v8 R2 仍为 NOT_RUN；
v7/v8 的 EVIDENCE_GAP 历史没有改成 PASS。
旧 `.p33acceptance` 由用户本人卸载的来源已确认，不重新整改、构建或补测。

索引在证据提交之后另行提交，已有索引行不改写。
本次只增加证据、索引、看板及本记录，不改变受验 profile、冻结合同或验收工具。

## 完整性复校

在 admission 工作树实际执行用户指定命令，退出码 0：

    python -X utf8 -B -S Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-3-v9.contract.json --matrix docs/acceptance-contracts/P3-3-v9/P3-3-v9.evidence-matrix.json --repo-root . --previous-contract docs/acceptance-contracts/P3-3-v8.contract.json --previous-matrix docs/acceptance-contracts/P3-3-v8/P3-3-v8.evidence-matrix.json

    VALIDATION=PASS contract=P3-3-v9 round=P3-3-V9-ACCEPTANCE-20260915-R2 overall=PASS

这是完整性复校，不是新验收轮次；未执行任何新产品测试、构建或硬件操作。
本次操作日志保留在 admission 工作树 `.cache/p3-3-closeout-20260915-01/`。
文本敏感信息预检的 12 处命中均为 CI 原始日志中的 shell 变量占位符，未出现密钥值；
证据提交仅对这些已核实误报使用全局 hook 提供的单次 secret-check 例外，
冲突标记与调试语句检查仍执行通过，未修改全局 hook、凭据或冻结日志。

## PR 和同步前置

初次 fetch 的远端 main 为 `0ef3cc14f6fdbece4f15b45864b94cb1007af735`。
实际合并差异不含 `app/bluetooth_flutter_Trace/docs/`，Pages 部署条件不成立；
Release/Cloudflare 发布须 tag 或显式发布 dispatch，本次均不执行。
仓库允许 merge commit，且 `delete_branch_on_merge=false`；不删分支或 worktree。
只检查本次 push/PR 自然触发的非发布 CI，不另行 dispatch 或重开历史验收。

静态检查发现治理测试 `tests/ota/test_acceptance_bundle.py` 仍把索引行数固定为 7，
且要求结果列严格等于 PASS；既有索引已包含后续历史条目。
本次不修改该受验 Validation 输入，也不改写真实索引结果规避检查；
合并是否可继续，以必要 CI 的实际结果及用户既定停止条件为准。

主工作树目前为 `dev/flutter/apk/p3-3-t1a`，HEAD
`c89c58f44dec1745980f0f2a54e612af48f6d32c`，不是 main。
同步预检发现 10 个既有 tracked 改动与待合入路径相交，
另有 9 个未跟踪文件与目标 tracked 路径重名；未尝试覆盖或切换。
完整路径清单及基线 SHA-256 留在本次缓存的 `main-sync-preflight.json`
和 `archive-baseline.json`。不以 stash、reset、清理或夹带提交消除这些改动。
主工作树安全同步、HEAD == origin/main 和收口记录入 main 均为结束前硬条件。

## 写入边界

用户仅授权主工作树 `D:\github\my\E-Track` 与其内的
`.cache\worktrees\p3-3-admission`；本次主动写入均在上述根目录内，
路径和完整父链已预检，无 reparse point；TEMP/TMP/TMPDIR/GH 缓存收敛至项目内。
既有 10 个 tracked 脏文件、384 个主工作树未跟踪文件及 25 个 admission
无关未跟踪文件已建立保留基线，不纳入本批提交。
admission 工作树、原始日志和唯一资产保留，不删除工作树。
未执行发布、部署、tag/Release、安装、卸载、清数据、OTA、J-Link、烧录或复位。

## 收口阻断后的追加授权与修复

PR https://github.com/Eitan-S-23/E-Track/pull/24 初轮实际 CI：
治理 run 34960469334 被固定索引行数断言打红；开发 run 34960338796 的双宿主
analyze/test 通过，但 Linux debug APK 在 packageDebug 阶段磁盘耗尽。
release APK/EXE run 34960469237、自动 MCU run 34960469219 成功，
Release、Pages 和 Cloudflare 注册跳过。失败记录保留，不覆盖为成功。

用户随后明确授权治理测试、开发 CI 的最小修复，以及主树原改动无损保全。
本批 post-bundle 治理/CI 变更影响 Validation 和指南所属 Governance，
不修改产品、冻结 profile、合同、校验器或旧证据；旧 v9 PASS 不冒充新 HEAD 的验收。
修复、独立复核与实测宿主结果见
`docs/ota-exec-notes/P3-3-closeout-ci-remediation-2026-09-15.md`。

主树 19 份待保全文件已保存原字节归档，并在本地专用分支
`archive/p3-3-root-before-main-20260915` 提交
`81f93ff7d3aa3f54edc5acf7c752c498eb7a65d6`；不推送、不并入 PR。
未删除或清理其他文件；原 t1a 分支保留。
新 CI、PR 合并及 main 同步仍待执行，整卡 Git 收口尚未完成。

## 最终合并与主树同步

上节“仍待执行”为修复提交前的历史状态，现由本节的实际结果接续。

- 证据提交：`5695abc5d7cd1402bd0815017a3e383c57571662`。
- 独立索引提交：`4df590b37c2e4f9f1f7e1aa82c47898c384164ba`。
- 治理/开发 CI 修复提交：`3110cd7af5fc6e63cc764dc639d1b4514acec486`。
- PR：https://github.com/Eitan-S-23/E-Track/pull/24。
- 合并时间：2026-09-15T13:04:17Z。
- merge commit：`c6465bd44121f244de25bf15103ccc7dd429f68c`。

合并前 GitHub 确認 approved head=3110cd7、base=0ef3cc1、MERGEABLE/CLEAN，
所有必要检查 completed SUCCESS；使用 `--merge --match-head-commit`，
未使用 auto/admin/squash/rebase、force-push 或删除分支选项。

| 必要 CI | 当前实际结果 |
|---|---|
| Acceptance Governance / 34970512157 | SUCCESS |
| Flutter Development Checks / 34970506983 | Linux、Windows SUCCESS；Linux debug APK build/verify/collect 全 PASS |
| Build APK and EXE / 34970511963 | Android release-mode APK、Windows EXE SUCCESS |
| MCU Firmware Build / 34970512071 | SUCCESS，仅自然 PR 触发 |

Release、GitHub Pages 和 Cloudflare 注册均 SKIPPED，未执行任何发布或部署。
旧失败 run 34960469334/34960338796 保留，不改写其结果。
开发 Linux 磁盘预检 free=14378385408 B，minimum=12884901888 B；
APK 完成后 `/dev/root` 可用 855 MiB（df 人类可读输出），
说明当前修复实际跑通，但未来冷工具链仍需关注磁盘容量，12 GiB 不是充分性保证。

安全同步顺序实测：fetch origin 后确认没有 worktree 检出 main；
root tracked clean，486 个 incoming 变更路径无未跟踪/忽略文件或父链碰撞；
用无强制的 `git fetch origin refs/heads/main:refs/heads/main` 快进本地 main，
再在指定主树执行 `git switch --no-overwrite-ignore main`。
主树 HEAD 和 origin/main 均为 c6465bd44121f244de25bf15103ccc7dd429f68c，
`git status --short --branch --untracked-files=no` 只显示 `main...origin/main`。

同步后只读审计 PASS：freeze_commit -> bundle_commit -> origin/main 可达，
367 份证据/报告 Git 对象与 bundle 相同，主树 363 份冻结文件原始 SHA-256 相同，
FREEZE-INDEX 与索引提交相同；post-bundle 差异仅为已批准的治理/开发 CI 和收口文档。
未在治理修改后的 HEAD 上重跑旧 v9 执行门禁，也没有新建正式验收轮次。

一次收口辅助审计误用了“Git fixture 隔离配置”启动模式，因丢失正常 autocrlf
配置而把检出行尾报告为脏；正常 Git status 无 tracked 差异。
改用真实工作树配置的同一只读审计后 PASS，未修改/还原文件或绕过门禁，
误报日志 `first-main-identity-audit.*` 原样保留。这不是产品或 v9 验收失败。

本节与看板作为后续文档提交通过 PR 落入 main，不仅留在已合并分支；
不记录本提交自身 SHA，最终文档合并后再快进主树并核对 HEAD == origin/main。
admission 工作树、原始日志、唯一资产、本地保全分支和 19 份原字节归档均保留。
本次主动输出仅在用户授权的两个项目根内，临时和 GH 缓存位于 admission
`.cache/p3-3-closeout-20260915-01/`；未启动 PowerShell，无已知项目外主动写入。
未执行本地 Flutter 构建、新的产品验收、手动 build-only/固件工作流、
Release/tag、部署、安装/卸载/清数据、OTA、J-Link、烧录或复位。
