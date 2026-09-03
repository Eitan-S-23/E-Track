# P3-2 收口证据（PR #16）

- 卡：P3-2「GET_INFO 设备身份链」，同批附带 P3-7 立卡
- 收口执行者：主会话（非 P3-2 实现方；本会话此前只立 P3-7 卡、冻结 P3-2 派工书、
  执行 P3-2 独立验收与 R10 补证）
- 用户授权：2026-09-03「可以收口」
- 结果：PR #16 已并入 `main`，本地 `main` 已快进并与 `origin/main` 一致
- 看板是 Governance profile 的 `top_file`，不记任何哈希（含 commit SHA），
  故全部哈希与运行号登记在本文件

## 1. 提交拆分与裁定

工作树上原本混着三批互不相干的改动。按「后一批不得夹带前一批」拆成三个提交：

| 顺序 | 提交 | 内容 | 规模 |
|---|---|---|---|
| 1 | `cfa07a5` | P3-7 立卡（含派工书冻结） | 5 文件 +253/-11 |
| 2 | `cb2ebdd` | P3-2 实现 + P3-2-v1 独立验收证据包 | 47 文件 +27581/-625 |
| 3 | `aeccad0` | P3-2 看板补更新：R10 由 ENV_BLOCKED 升级为已观测 | 1 文件 +1/-1 |

顺序不可交换，理由是可校验性：`cb2ebdd` 的 Governance manifest 绑定的正是该提交里
的看板字节，而 R10 是冻结之后才观测到的加强项。若把 R10 的看板更新并入 `cb2ebdd`，
证据包在自己的落地提交上就校验不过；若把看板回写单独推迟到最后，`cb2ebdd` 里的
Governance manifest 又会绑定一份「还没写回验收结论」的看板。所以固定为
**先落冻结点、再落晚于冻结的内容**。

拆分手法：看板 `PLAN-OTA-EXEC.md` 是混合行尾，只能按字节整行操作。用
`.cache/closeout/split_board.py` 把 HEAD 与最终版做行级 opcode 比对，逐块按批次归属
（`p37` 取最终版、`p32` 保留 HEAD、两处需要自定义中间态），脚本内以断言钉死
「变更块数 == 归属表条目数」「每块都已归属」「阶段计数行格式未变」「§10 新增行恰为
2 且顺序为 P3-7 在前」，任一不符即拒绝写出。提交 1 落地后再从
`.cache/closeout/PLAN-OTA-EXEC.final.md`（SHA-256
`EDA0528A03D430D802B5403157ED85E4124CDBAA088A8CD1E1D7D699984B14B2`）按字节还原，
还原后 `git diff --numstat` 为 9/3，与提交 2 应携带的看板改动完全吻合。

## 2. 合并方式：merge 而非 squash（与 P3-6 的相反裁定）

P3-6 用 squash，目的是让刻意注入 CRC 缺陷的临时提交不进入 `main` 可达历史。
本次**必须用 merge**，理由相反且更硬：squash 会把三个提交压成一个，
`cb2ebdd` 这个可校验冻结点随之消失，P3-2-v1 证据包将在 `main` 的任何提交上都
无法复校。仓库 15/16 的 merge 惯例本身也支持这一选择。

合并结果：合并提交 `0e4780ed6c87497ea1252aaa27b4f59cb491c5e1`，
时间 `2026-09-03T05:02:15Z`。`git merge-base --is-ancestor cb2ebdd main` 为真，
冻结点在 `main` 上可达、可 `git checkout` 复校。特性分支 `ota/p3-7-card` 按仓库
惯例保留未删。

## 3. 合并前 CI 全绿

| 检查 | 结果 | 耗时 | 运行号 |
|---|---|---|---|
| Build firmware (arm-none-eabi-gcc) | pass | 1m10s | 33717103433 |
| Validate acceptance and build governance | pass | 45s | 33717103387 |
| Detect changed paths | pass | 9s | 33717103347 |
| Build Android APK / Windows EXE / Release / Pages | skipping | — | 33717103347 |
| Register firmware to Cloudflare | skipping | — | 33717103433 |

固件构建绿是干净 checkout 下的 Ubuntu + arm-none-eabi-gcc 结果，覆盖了本卡新增的
`Libraries/OTA/ota_device_info.c`；`AGENTS.md` 记载的反斜杠 `#include` 陷阱未复发。
Acceptance Governance 绿覆盖了提交 1 对 `tests/ota/test_acceptance_bundle.py`
钉死断言的修改（可派单集合五项扩六项）。

## 4. 入库后的三项实测（不是推断）

### 4.1 冻结点校验通过

在提交 `cb2ebdd` 的内容状态下（全部改动已入库、看板尚未做 R10 更新）：

```text
python -X utf8 -B Tools/acceptance/validate_bundle.py \
  --contract docs/acceptance-contracts/P3-2-v1.contract.json \
  --matrix docs/acceptance-contracts/P3-2-v1/P3-2-v1.evidence-matrix.json \
  --repo-root D:/github/my/E-Track
VALIDATION=PASS contract=P3-2-v1 round=P3-2-V1-FREEZE-20260903-01 overall=PASS
退出码 0
```

### 4.2 漂移范围精确等于本次回写

`aeccad0` 之后在 `main` 顶端复跑同一命令：

```text
ERROR: input manifest worktree length mismatch: PLAN-OTA-EXEC.md
ERROR: input manifest worktree SHA-256 mismatch: PLAN-OTA-EXEC.md
VALIDATION=FAIL errors=2
退出码 1
```

**errors=2 且全部且仅为看板的长度与 SHA-256**，这条比单纯的 PASS 更有信息量：
校验器是从工作树重新枚举并逐文件读取三个 profile 的真实文件的，
Production 2920 个 + Validation 152 个 + Governance 其余 25 个文件在
**一次真实的分支切换检出之后**仍逐字节匹配冻结值。

### 4.3 F-1 的 `-text` 护栏在真实检出后生效

`git checkout main` 重写了工作区全部文件，随后：

```text
i/lf    w/lf    attr/-text   Libraries/OTA/ota_device_info.c
i/lf    w/lf    attr/-text   MDK-ARM_F435/cmake-generated/CMakeLists.txt
i/mixed w/mixed attr/        PLAN-OTA-EXEC.md
i/-text w/-text attr/-text   docs/acceptance-contracts/P3-2-v1/artifacts/realdevice/info_frame.bin
i/crlf  w/crlf  attr/-text   docs/acceptance-contracts/P3-2-v1/manifest-production/source-manifest.json
```

`CMakeLists.txt` 此前会触发 Git 的
「LF will be replaced by CRLF the next time Git touches it」警告，是 F-1 判定
「在纯 LF 工作副本上冻结的 Production 指纹先天不可复现」的直接依据。补护栏后它
**首次**变成 `i/lf w/lf` 字节稳定，且 §4.2 的错误集里没有它，构成入库后闭环证据。

看板本身刻意**不加** `-text`：它的 index blob 已含 CR，Git 的 AUTO 启发式对
「已含 CR 的 blob」两个方向都不转换，故按字节提交即逐字节保真；`.gitattributes`
自身的维护规则也禁止为 index 已含 CRLF 的文件新增 `-text`。实测入库字节与工作区
字节 SHA-256 相同（`641B97D02B8C5FD3D6109AED82447690295FA0EF8FEEBD04D24F25720F5CC5FD`，
415046 B，CRLF 724 / 裸 LF 252）。

## 5. 一处「预期不可复跑」须留档

`tests/ota/p3_2_verify_scope.py` 在收口后必然转红（23 项中 2 项失败），
不是回归：

```text
FAIL 本卡未产生已提交改动（实现 agent 不 commit，§0 规则 8）: got=50 want=0
FAIL P3-2 卡内改动 9 项（2 身份链源 + 1 HAL + 2 构建注册 + 2 测试 + 2 笔记）: got=0 want=9
```

两项都是**收口前快照断言**：前者统计 `merge-base..HEAD` 的变更文件数（收口提交
落地后必然非 0），后者统计未提交的工作区差异（入库后必然为 0）。绿色观测已按字节
冻结在 `docs/acceptance-contracts/P3-2-v1/commands/verify-scope.log`；
`validate_bundle.py` 读该日志与产物字节、不重跑核验器，故 §4.1 的 PASS 不受影响。

须说清一点：这两项的绿色状态**任何提交都无法复现**——它们断言的是「改动尚未提交」，
而那是一个工作区状态，不是某个提交的树。可复核的只有其余 21 项，以及冻结日志本身
（校验器会读文件复核其路径、大小与 SHA-256，日志被篡改会被打红）。

治理门禁不受影响：回写后 `tests/ota/test_acceptance_bundle.py`
仍为 `65 passed, 82 subtests passed`。

## 6. 主分支同步闭环

本仓库**没有任何 worktree 检出 `refs/heads/main`**（实测三个 worktree 分别在
`ota/p3-7-card`、`p2-4-20260731`、`p2-5-20260801`），故无法按规约字面在「main
worktree」里执行 `git merge --ff-only`。采用等价且同样受快进检查约束的做法：

```text
git fetch --prune origin            → dd0a995..0e4780e  main -> origin/main
git rev-list --left-right --count main...origin/main   → 0  4   （无分叉）
git fetch origin main:main          → dd0a995..0e4780e  main -> main
git rev-list --left-right --count main...origin/main   → 0  0
git checkout main                   → Switched to branch 'main'
git rev-parse HEAD                  → 0e4780ed6c87497ea1252aaa27b4f59cb491c5e1
git rev-parse origin/main           → 0e4780ed6c87497ea1252aaa27b4f59cb491c5e1
git status --short --branch         → ## main...origin/main  （无 ahead/behind）
```

`git fetch <remote> <src>:<dst>` 对非当前分支只接受快进，非快进会被拒绝，
语义与 `--ff-only` 一致；未使用 `reset` 或任何强制覆盖。同步后把主 worktree
切到 `main`，使项目进度从已同步的主分支读取。7 个既有未跟踪文件
（`.cache-cmake-time-test.cmake`、`.claude/cc_recover_s4.js`、
`.claude/ccprobe_hash.js`、`.claude/ccprobe_plan.js`、
`.claude/write_p3_2_acceptance_board.py`、`.claude/write_r5_phase0_board.py`、
`.claude/write_r5_ruling_board.py`）全部保留未动。

### 6.1 PR #17 的同步闭环，并补正 §6 的一句话

收口回写自身也走了一次 PR：#17，合并提交 `576a863b5ca0619d95e52c4153f26585e85aed91`，
时间 `2026-09-03T05:18:45Z`，以 merge 方式（与 P3-6 收口回写的 PR #15 同型）。
合并前检查：`Validate acceptance and build governance` pass 45s
（运行号 33718213199）、`Detect changed paths` pass 8s（运行号 33718213200）、
APK/EXE/Release/Pages 四项 skipping，`mergeable=MERGEABLE state=CLEAN`，无 pending。

`MCU Firmware Build` 这次**根本没被触发**，不是被跳过：`firmware-build.yml` 的
`paths:` 过滤只列 `USER/** ArduinoAPI/** Libraries/** MDK-ARM_F435/** boot/**
cmake/** tests/boot/** tests/ota/test_ota_*.{c,py} tests/ota/stubs/**
tests/ota-vectors/** vendor/** Simulator/LVGL.Simulator/lv_conf.h` 与自身，
`PLAN-OTA-EXEC.md` 和 `docs/ota-exec-notes/**` 都不在内，属设计中的 monorepo 路径
隔离。本卡源码的固件构建绿记在 §3（PR #16 运行号 33717103433），不因本次未触发
而缺失。

**补正 §6 的措辞**：§6 说「本仓库没有任何 worktree 检出 `refs/heads/main`，故无法按
规约字面在 main worktree 里执行 `git merge --ff-only`」。这句话在当时那一刻成立，
但**不该被后续 agent 当成先例照抄**——字面路径其实做得到：主 worktree 的 tracked
工作区干净时（只剩既有未跟踪文件），先把它切到 `main`，再执行规约原文的命令即可。
本次就是这么做的：

```text
git fetch --prune origin          → 0e4780e..576a863  main -> origin/main
git worktree list --porcelain     → 三个 worktree 分别在 ota/p3-2-closeout、
                                     p2-4-20260731、p2-5-20260801（仍无 main）
git rev-list --left-right --count main...origin/main   → 0  2   （无分叉）
git checkout main                 → Switched to branch 'main'（7 个未跟踪文件未被覆盖）
git merge --ff-only origin/main   → Updating 0e4780e..576a863  Fast-forward
git rev-parse HEAD                → 576a863b5ca0619d95e52c4153f26585e85aed91
git rev-parse origin/main         → 576a863b5ca0619d95e52c4153f26585e85aed91
git status --short --branch       → ## main...origin/main  （无 ahead/behind）
git merge-base --is-ancestor cb2ebdd main → 真（冻结点仍可达）
```

**优先级**：以后遇到「无 worktree 检出 main」，先试「切主 worktree 到 main +
`git merge --ff-only`」；只有当主 worktree 的 tracked 改动无法安全离开当前分支时，
才退到 §6 那种同样受快进检查约束的引用更新形式，并说明退让理由。

**递归终止**：本节是文档追加，不改看板字节、不属任何 manifest profile，故不再产生
新的看板回写义务。本节之后的纯文档跟进提交不需要再写同类附录，否则「记录同步 →
产生新合并 → 又要记录同步」会无限递归。P3-2 收口至此闭环。

## 7. 收口回写导致的指纹漂移（声明）

本次收口回写（P3-2 卡状态「待收口」→「已收口」、新增「- 收口:」行、§10 追加一条）
再次改动 `PLAN-OTA-EXEC.md`，使 P3-2-v1 的 Governance 指纹继续漂移。这与 §4.2 是
同一性质：**每轮证据包只在其冻结提交上可校验，不是永久有效**。要复校 P3-2-v1
请 `git checkout cb2ebdd`。P3-7 后续的状态回写同样会造成漂移，属正常状态，
不得回改任何冻结字节来「修复」。

`docs/ota-exec-notes/` 不属任何 manifest profile，故本文件的新增对三类指纹中性。

## 8. 交叉引用

- 第 1 轮独立验收报告（全部冻结指纹登记于此）：
  `docs/ota-exec-notes/P3-2-acceptance-round1.md`
- R10 冻结后补证：`docs/ota-exec-notes/P3-2-acceptance-r10-addendum.md`
- 实现方证据与 research：`docs/ota-exec-notes/P3-2-implementation-evidence.md`、
  `docs/ota-exec-notes/P3-2-identity-research.md`
- 冻结合同与证据包：`docs/acceptance-contracts/P3-2-v1.contract.json`、
  `docs/acceptance-contracts/P3-2-v1/`
- 审查报告：`.claude/verification-report-p3-2.md`
- P3-7 立卡取证：`docs/ota-exec-notes/P3-7-card-creation.md`
- P3-6 收口先例（squash 裁定与本次相反）：`docs/ota-exec-notes/P3-6-closeout.md`
