# P3-6 收口证据（哈希登记）

本文件承载 P3-6 收口的全部哈希、运行号与命令输出。**哈希不写进 `PLAN-OTA-EXEC.md`**：看板是
`Tools/provenance/manifest_profiles.json` 里 Governance profile 的 `top_file`，把指纹（含 commit
SHA）写进看板会构成「回写看板 → Governance 指纹变化 → 合同内记录的指纹失效 → 合同重算 →
合同哈希变化」的不收敛闭环。`docs/ota-exec-notes/` 不被任何 profile 枚举，是哈希登记的既有落点。
本次沿用 P3-1 收口的同一口径（见 `docs/ota-exec-notes/P3-1-closeout-evidence.md`）。

执行者：主会话（Claude），2026-09-02，用户明确确认后执行。
本轮验收结论未被本次收口改动：单轮结果 **PASS**，轮次 `P3-6-V1-FREEZE-20260902-01`，
13 判据全 `EXECUTED PASS` 无 `REUSED`，综合评分 94/100。
验收报告 `docs/ota-exec-notes/P3-6-acceptance-report.md`，审查报告 `.claude/verification-report-p3-6.md`。

---

## 1. 收口形状

| 项 | 值 |
|---|---|
| 特性分支 | `ota/p3-6-ci-wiring`（实现 + 验收资产同分支） |
| PR | <https://github.com/Eitan-S-23/E-Track/pull/14> |
| 被验收 Head | `a9cf6f7fb0802059b52b67225851260e81728f90` |
| 验收资产提交 | `7833303cc036d1609db0224b39480a52063300ed`（39 文件，+24725 / -2） |
| 合并方式 | **squash**（用户裁定，理由见 §2） |
| main 上的 squash 提交 | `fa320bead2cce90b38bf211ca757f846822ded25`（2026-09-02T14:25:41Z，44 文件，+25330 / -8） |
| 合并前基线 main | `ded14e8cb476a98191bcaca2d9b83be71471f044` |
| 本次收口回写分支 | `ota/p3-6-closeout`（基点 `fa320be`） |

squash 提交的 44 文件是**整分支净效果**（含实现方的 workflow 改动、两份实现证据笔记、派工书与
`test_acceptance_bundle.py`），而 `7833303` 的 39 文件只是验收资产那一笔。两者树等价已实测：

```text
$ git diff --stat 7833303 fa320be
（无输出 —— squash 后的树与被验收的树逐字节相同）
```

刻意排除并保持未跟踪（先前会话遗留，与本卡无关；`.claude/` 未被 `.gitignore` 忽略）：
`.cache-cmake-time-test.cmake`、`.claude/cc_recover_s4.js`、`.claude/ccprobe_hash.js`、
`.claude/ccprobe_plan.js`、`.claude/write_r5_phase0_board.py`、`.claude/write_r5_ruling_board.py`。
交付集逐路径显式 `git add`，未用 `git add -A` / `git add .`。

关键资产哈希（SHA-256，收口时点）：

| 路径 | 长度 | SHA-256 |
|---|---|---|
| `docs/acceptance-contracts/P3-6-v1.contract.json` | 27314B | `E80966AAA3EC17C4A00F3B8A7378DA31AB13F629135A3E8685F794F9D2276A4C` |
| `docs/acceptance-contracts/P3-6-v1/P3-6-v1.evidence-matrix.json` | 14707B | `BBC78069DFF22B820B6EF2E998CF063DF1FE85FA57479EEC87C41A8862D4B7CB` |
| `.gitattributes`（追加 4 行护栏后） | 13681B | `E5840717567AAD1FE825D00A3C3AF356F997234829C3C28AEC903A2D11F8226C` |

---

## 2. 合并方式裁定：为什么本卡用 squash

### 2.1 事实

分支 5 个提交中，第 3 个 `7b58ed6fd8ee5a9124c5d3383c13e57622f4586b` 向
`Libraries/OTA/ota_ble_frame.c` **刻意注入 CRC 缺陷**，用于取得真实的 CI 红色运行；
第 4 个 `e3f9b1ab75892ebe06302fe79f0fa41f5014b4ce` 完整还原（验收判据 C09 已用 11729 字节与
SHA-256 `07b20f99c37910cc…` 核实还原到位，与 `main` 一致）。最终代码与不注错的做法完全相同。

### 2.2 唯一实害：`git bisect` 会得出错误结论

`git bisect` 默认遍历被合并分支内部的提交（只有 `--first-parent` 才跳过）。若以 merge 提交并入，
`7b58ed6` 就成为从 `main` 可达的历史点，二分排查途经该点会拿到 CRC 有缺陷的
`Libraries/OTA/ota_ble_frame.c`，从而**把无关缺陷误判为 culprit**——这不只是浪费一次编译，
而是给出错误答案。概率低，但规避成本为零，故规避。

### 2.3 偏离仓库惯例的如实声明

`main` 上 112 个提交中有 15 个 merge 提交——**此前每个 PR 都用 merge 提交**，本次是首次偏离。
偏离理由仅一条：本 PR 是首个包含刻意注错提交的 PR。此判定不作为后续卡的默认做法。

### 2.4 squash 不损可审计性

- PR #14 的提交列表与 `refs/pull/14/head` 仍在远端，5 个提交按 SHA 可查。
- fail-closed 反证的运行 JSON 与步骤日志已**按字节冻结**在
  `docs/acceptance-contracts/P3-6-v1/ci/`（9 份采集件，哈希见验收报告 §5.1）。
- squash 提交正文**主动写明**注错-还原史与 squash 原因，因此该事实可从 `git log main` 直接发现，
  而非被隐藏。
- 未采用改写历史（force-push）方案：那会使 CI 运行 33621049995 的 Head SHA 失去指向、
  打断 `ci/pr-14.json` 的 5 提交绑定与 C08 的 `defect_then_restore=1` 派生，
  恰好销毁本卡存在意义所在的反证链。

### 2.5 目标已核实（非断言）

```text
$ git merge-base --is-ancestor 7b58ed6 main
EXIT=1        # 非零 = 不可达 → 二分排查不会检出到缺陷树

$ git log --oneline -2 main
fa320be P3-6：BLE 帧层测试接入 firmware-build.yml 与 P3-6-v1 独立验收 (#14)
ded14e8 Merge pull request #13: P3-1 收口回写（看板状态、会话日志与收口证据笔记）
```

---

## 3. 入库后门禁：`-text` 护栏的决定性证据

`.gitattributes` 追加的 4 行护栏（4 个 `tests/ota/p3_6_verify_*.py`）与证据包同批入库。本机
`core.autocrlf=true`，纯 LF 的 Validation profile 成员若无护栏，真实检出会把冻结指纹打红。
证据包自身由既有第 19 行 `/docs/acceptance-contracts/** -text` 覆盖。

护栏生效的实测（`git check-attr text` 对合同、矩阵、4 个 harness、
`manifest-validation/source-manifest.txt`、`commands/verify-scope.log`、`ci/step-33621049995.txt`
均为 `text: unset`），以及**提交入库后**复跑校验器：

```text
$ python -X utf8 -B Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-6-v1.contract.json --matrix docs/acceptance-contracts/P3-6-v1/P3-6-v1.evidence-matrix.json --repo-root D:/github/my/E-Track
VALIDATION=PASS contract=P3-6-v1 round=P3-6-V1-FREEZE-20260902-01 overall=PASS
EXIT=0
```

这一条是**在 `7833303` 已落盘之后**跑的：`git commit` 不改变工作树任何字节，三份 manifest 枚举的
是工作树而非 git 跟踪态（4 个当时未跟踪的 harness 脚本已在 Validation 的 146 个文件内），
故入库不会使指纹漂移。按验收规约第 3 条，仅 `HEAD` 变化不触发产品复验。
pre-commit hook 亦通过（`✅ Pre-commit 检查通过`）。

---

## 4. CI（PR #14，合并前全检查绿）

```text
$ gh pr checks 14 --watch
Build firmware (arm-none-eabi-gcc)          pass  1m6s     run 33641715933
Validate acceptance and build governance    pass  47s      run 33641715878
Build APK and EXE Release                   （各 job 按路径过滤 skipping）run 33641716005
EXIT=0
```

两条硬门禁的意义：

- `Build firmware` 绿满足 `AGENTS.md`「干净 checkout 构建绿」硬条件，且**该运行已包含本卡新接入的
  两条 BLE 测试**——即接线在 Ubuntu + arm-none-eabi-gcc 真实环境下确实被执行且通过，
  不是只在本机 Windows 上过。
- `Validate acceptance and build governance` 绿意味着新增的合同、矩阵与 4 个 harness 脚本
  在 CI 侧也通过治理校验，满足规约第 8 条「schema/校验器/manifest 变化必须过
  `acceptance-governance.yml`，不得以本地测试通过代替 CI 接线」。

---

## 5. 合并后收口闭环（`AGENTS.md`§「Git / Worktree 收口规约」）

```text
$ git fetch --prune origin
   ded14e8..fa320be  main -> origin/main

$ git worktree list --porcelain
worktree D:/github/my/E-Track                  branch refs/heads/ota/p3-6-ci-wiring
worktree D:/github/my/E-Track-p2-4-20260731    branch refs/heads/p2-4-20260731
worktree D:/github/my/E-Track-p2-5-20260801    branch refs/heads/p2-5-20260801
                                               # 无任何 worktree 检出 refs/heads/main

$ git fetch origin main:main                   # 等价的非破坏性 ff-only 推进
   ded14e8..fa320be  main -> main

$ git rev-parse main         fa320bead2cce90b38bf211ca757f846822ded25
$ git rev-parse origin/main  fa320bead2cce90b38bf211ca757f846822ded25   # 一致
```

**与 P3-1 收口的处置差异（须看清，勿照抄）**：P3-1 时主 worktree 本身持有 `main`（被切到特性分支），
处置是切回 `main` 再 `merge --ff-only`。本次主 worktree 持有 `ota/p3-6-ci-wiring`，本地 `main`
是无检出的纯引用，因此用 `git fetch origin main:main` 推进——该 refspec 在非快进时会被 git 拒绝，
语义等同 `--ff-only`，且不需要切换工作树、不动任何工作树字节。**未使用 reset 或强制覆盖**。
6 个刻意排除的未跟踪文件全程保留。

---

## 6. 合并后 Governance 漂移声明（不得隐瞒）

回写看板会改变 `PLAN-OTA-EXEC.md` 字节 → Governance manifest 指纹变化 → P3-6-v1 合同内记录的
`governance.manifest_sha256`（`123C9F7D7172B73CEF4B0EE4BC6AD7D4E2E77B86282648892BBE4214A8483D4E`）
与工作树不再匹配 → `validate_bundle.py` 对 P3-6-v1 转红。

这是**已冻结合同在收口回写后的正常状态**，不是缺陷，也不改判本轮 PASS。回写后两条门禁的实测
（不做美化）：

```text
$ python -X utf8 -B Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-6-v1.contract.json --matrix docs/acceptance-contracts/P3-6-v1/P3-6-v1.evidence-matrix.json --repo-root .
ERROR: input manifest worktree length mismatch: PLAN-OTA-EXEC.md
ERROR: input manifest worktree SHA-256 mismatch: PLAN-OTA-EXEC.md
VALIDATION=FAIL errors=2
EXIT=1

$ python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle
Ran 65 tests in 36.247s
OK
EXIT=0
```

两点须看清：

1. 转红的**全部**原因就是 Governance `top_file` 的长度与 SHA-256 变了，`errors=2` 且再无其他条目
   ——漂移范围精确等于本次回写，未夹带任何产品或验收资产变化。
2. `tests/ota/test_acceptance_bundle.py` 65 项**仍全绿**。它是
   `.github/workflows/acceptance-governance.yml` 的门禁内容，故本次回写不会打红 CI。

可复现性由**锚定提交**承载：任何人可 checkout `fa320be`（看板为冻结时字节）并复验 PASS，见 §3。
不因此重算合同或升 v2——本轮验收已 PASS，为容纳收口回写而重新冻结属把流程面当结论面改。
若未来复用 P3-6-v1 的判据，须按规约第 3 条走 `rerun-plan.json` 比较，不得人工声明未失效。

---

## 7. 看板回写的实际改动（3 处，`git diff --numstat` = `3  1`）

- **P3-6 卡状态行**：括注内 `尚未收口` → `已收口`，并把 `收口待主会话在用户确认后执行` 替换为
  收口结论（squash 裁定、PR 号、注错提交未进入 main 可达历史、三条流水线全绿）。
  状态**取值仍为 `完成`** —— 看板 §0 第 10 条把取值钉死为 `待办/进行中/阻塞/完成`，
  不自造 `已收口` 作为取值；亦未覆盖实现方的「认领」字段。
- **新增 `- 收口:` 行**：插在 `- 独立验收:` 之后，记合并方式、CI 状态、入库后校验器结论、
  注错提交不可达的核实结果、闭环结果与本文件路径。
- **§10 会话日志**：在文件末尾追加 1 条（该区既有条目为「最新在后」）。

编辑方式：**按字节的 Python 脚本**（`.cache/p36-accept/write_closeout_board.py`），
以 `\n` 切分并保留行尾 `\r` 后重连，逐行 EOL 原样保留。**未使用 Edit 工具**——看板 EOL 混合，
Edit 会整体规范化并混入上百行伪变更。

EOL 与无哈希自检（机器核对）：

```text
CRLF 707 → 709（恰为 2 条插入行）      bare LF 246 → 246（不变）
「内容相同仅行尾不同」的删加对 = 0     BOM = False
新增行内 >=7 位十六进制串 = ['20260902']   # 唯一命中是日期，非哈希
```

**看板内不含任何哈希**（含 commit SHA）：sha 全部落在本文件。追溯性不损失——PR #14 唯一确定
squash 提交，本文件 §1 亦直接登记。注：看板 §10 既有条目中存在 `PR #9 → bc13f18` 这样的
先例写法，本次仍按更严口径不写 SHA。

---

## 8. 遗留的两项不阻断发现

定性、影响与建议见验收报告 `docs/ota-exec-notes/P3-6-acceptance-report.md` §8，本处不复制
（内容唯一性规则：引用而非复制）。两项均**不影响本轮 PASS**，且刻意不在本次收口里夹带修复：

1. **CI 步骤名与实际内容漂移**（`Test Boot fw_header validator vectors` 实跑 8 条测试）：
   本卡接线前既已存在（基线 6 条中已含 3 条超出该名），本卡只是从 6 放大到 8。改名要动
   `.github/workflows/firmware-build.yml`——Production profile 的 `top_file`，会使刚通过的验收在
   新 HEAD 上失效，须新立卡、升 P3-6-v2 合同并走完整新一轮，代价与收益不成比例，且在本卡冻结
   范围之外。
2. **注错提交 `7b58ed6` 曾在分支历史**：其真正的处置手段就是合并方式选择，已由 §2 的 squash
   落实并核实。

---

## 9. 刻意未做

- **未改** `.github/workflows/firmware-build.yml` 的步骤名（见 §8 发现 1）。
- **未删** 特性分支 `ota/p3-6-ci-wiring`：保留以便 PR #14 的 5 个提交与反证链可按 SHA 审计。
- **未改写历史**（无 force-push）：理由见 §2.4。
- **未改** 任何产品源、验收资产字节、合同版本，或契约文件
  （`PLAN-OTA.md`、`docs/ota-binary-contracts.md`）。
- **未回改** P3-1-v2 的 Production 指纹（DEV-3 已如实声明漂移，冻结资产禁止回改）。
- 临时产物全部落仓库内已忽略的 `.cache/p36-accept/`，无仓库外写入。
