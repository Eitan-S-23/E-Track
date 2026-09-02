# P3-1 收口证据（哈希登记）

本文件承载 P3-1 收口的全部哈希与命令输出。**哈希不写进 `PLAN-OTA-EXEC.md`**：看板是
`Tools/provenance/manifest_profiles.json` 里 Governance profile 的 `top_file`，把合同/矩阵/manifest
哈希写进看板会构成「回写看板 → Governance 指纹变化 → 合同内记录的指纹失效 → 合同重算 →
合同哈希变化」的不收敛闭环。`docs/ota-exec-notes/` 不在任何 profile 的枚举范围内，是哈希登记的
既有落点。

执行者：非实现、非本轮验收的收口会话（Claude），2026-09-02。
本轮验收结论未被本次收口改动：单轮结果 PASS，轮次 `P3-1-V2-FREEZE-20260902-01`，
17 判据全 `EXECUTED PASS`。报告 `docs/ota-exec-notes/P3-1-acceptance-verification.md`。

## 1. 收口形状

| 提交 | 时间 | 范围 | 文件数 |
|---|---|---|---|
| `bd12ce1115023731f8378b092c6efeda3ad7a3d5` | 2026-09-02T17:00:45+08:00 | `.gitattributes` EOL 护栏 | 1 |
| `a305f66682444742aa68bd2db5de128545dfaf22` | 2026-09-02T17:03:13+08:00 | 产品实现 | 19 |
| `1db4fc6d6d8f86d091c026392960d67a7e2e9a05` | 2026-09-02T17:05:17+08:00 | 验收资产与看板 | 41 |

- 分支 `ota/p3-1-ble-frame-closeout`（基点 `77e14cf`），PR <https://github.com/Eitan-S-23/E-Track/pull/12>
- Merge commit `b36b868b91ad26e03ea4f5867a2a9a21cab0e6d3`（2026-09-02T17:14:03+08:00）
- 交付集 61 个文件；全部逐路径显式 `git add --pathspec-from-file`，未用 `git add -A` / `git add .`
- 刻意排除并保持未跟踪（先前会话遗留，`.claude/` 未被 `.gitignore` 忽略）：
  `.cache-cmake-time-test.cmake`、`.claude/cc_recover_s4.js`、`.claude/ccprobe_hash.js`、
  `.claude/ccprobe_plan.js`、`.claude/write_r5_phase0_board.py`、`.claude/write_r5_ruling_board.py`

关键资产哈希（SHA-256，收口时点）：

| 路径 | 长度 | SHA-256 |
|---|---|---|
| `docs/acceptance-contracts/P3-1-v2.contract.json` | 30066B | `E38FF2A6AD38806BDCD8AF589DEC3BFC3D0BEBD5C4837C572C482F97D2D99424` |
| `docs/acceptance-contracts/P3-1-v2/P3-1-v2.evidence-matrix.json` | 19335B | `81703655EFA4C4FDC4F14DB6F4D90C4C7DE9929EF2517F7920E462047EADC9D7` |
| `.gitattributes`（护栏后） | 13463B | `7C652505A8BDC45999611A207498763EB8C8AAF79A7F459FCA24A9CD1237C8C2` |

## 2. 提交前门禁（两条，原始输出）

```text
$ python -B Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-1-v2.contract.json     --matrix docs/acceptance-contracts/P3-1-v2/P3-1-v2.evidence-matrix.json --repo-root .
VALIDATION=PASS contract=P3-1-v2 round=P3-1-V2-FREEZE-20260902-01 overall=PASS
EXIT=0

$ python -B -m unittest tests.ota.test_acceptance_bundle
Ran 65 tests in 41.353s
OK
EXIT=0
```

## 3. EOL 护栏：为什么是收口的必要前置

派工书未预见此项。本机 `core.autocrlf=true`，收口必然包含把主 worktree 切回 `main` 并
`merge --ff-only`，该 checkout 会经过真实的行尾过滤器。

用临时索引（`GIT_INDEX_FILE` + `read-tree HEAD` + `add --pathspec-from-file` +
`checkout-index --prefix=`）做非破坏性往返实测：**60 个交付文件中 20 个纯 LF 文件会被改写为
CRLF**，其中 **18 个是 P3-1-v2 合同 Production/Validation manifest 的绑定路径**。
`Tools/acceptance/validate_bundle.py` 的 `validate_input_manifests` 会用
`_collect_profile_records` 重新枚举工作树并逐个比对 `Length` 与 `SHA256`，因此不加护栏，
刚冻结的指纹在任何全新克隆上必红。

处置：按 `.gitattributes` 文件头明文的「只增不改」维护规约追加 18 条 `-text`。追加前逐条验证
其前置条件成立（工作树字节 == 索引 blob，20/20）；条目插入排序位置，`git diff --numstat`
为 `18  0`（纯新增，无删除行）；条目数 236→254，长度 12714→13463B，CRLF 计数保持 0。

不纳入的 2 类：

- `tests/ota/test_ota_ble_frame.c`：索引 blob 内已含 CRLF，`autocrlf` 的 safer 规则本就逐字节保留。
- `docs/ota-exec-notes/P3-1-build-evidence.md`、`P3-1-research-ble-transport.md`：不属任何
  manifest profile；机器扫描确认证据矩阵完全不引用 `docs/ota-exec-notes/`，合同内唯一提及是
  `.implementation_ref` 的路径引用（无哈希绑定）。故其 CRLF 转换不影响任何指纹。

护栏的指纹中性由三条支撑：`.gitattributes` 不属任何 profile；不被任何工具或测试引用；不是
`.github/workflows/acceptance-governance.yml` 的 paths 触发项。改动后两条门禁复跑仍全绿（见 §2）。

## 4. 锚定证明（真实检出，非断言）

沿用 P2-6-v2 建立的锚定口径。对收口 HEAD `1db4fc6` 建临时 worktree 做**真实 checkout**
（完整过滤器路径，最接近全新克隆），再在该检出内自洽复验：

```text
bound paths      = 3083
absent in clone  = 0
byte mismatch    = 0

（在全新检出内，--repo-root 指向该检出）
VALIDATION=PASS contract=P3-1-v2 round=P3-1-V2-FREEZE-20260902-01 overall=PASS   EXIT=0
Ran 65 tests in 36.846s  OK                                                     EXIT=0
```

3083 = Production 2918 + Validation 142 + Governance 24 去重后的并集，由
`validate_bundle.py._collect_profile_records` 枚举。交付集侧另单独比对：61/61 中仅 §3 所述
2 个非绑定笔记有差异，其余逐字节相同。

**合并后在真实主工作树上复验（护栏在实战往返中生效的决定性证据）**：

```text
（switch main → merge --ff-only origin/main 之后）
VALIDATION=PASS contract=P3-1-v2 round=P3-1-V2-FREEZE-20260902-01 overall=PASS   EXIT=0
```

## 5. CI（PR #12，两条硬门禁）

```text
Build firmware (arm-none-eabi-gcc)          pass  1m0s
Validate acceptance and build governance    pass  41s
Detect changed paths                        pass  11s
（Android/Windows/Pages/Release/Cloudflare 均 skipping）
```

`Build firmware` 绿即满足 AGENTS.md「干净 checkout 构建绿」硬条件；本轮新源全部使用 POSIX
正斜杠 `#include`，未复现 PRE-4 的反斜杠不可移植问题。

## 6. 合并后收口闭环（AGENTS.md「Git / Worktree 收口规约」）

```text
$ git fetch --prune origin
   77e14cf..b36b868  main -> origin/main

$ git worktree list --porcelain
worktree D:/github/my/E-Track                    branch refs/heads/main
worktree D:/github/my/E-Track-p2-4-20260731      branch refs/heads/p2-4-20260731
worktree D:/github/my/E-Track-p2-5-20260801      branch refs/heads/p2-5-20260801

$ git merge --ff-only origin/main        # 在主 worktree D:/github/my/E-Track
（fast-forward，EXIT=0）

$ git rev-parse HEAD        b36b868b91ad26e03ea4f5867a2a9a21cab0e6d3
$ git rev-parse origin/main b36b868b91ad26e03ea4f5867a2a9a21cab0e6d3   # 一致

$ git status --short --branch
## main...origin/main                     # 无 ahead/behind
```

说明：定位主 worktree 时 `git worktree list` 一度显示**无任何 worktree 检出
`refs/heads/main`** —— 因为持有 main 的正是主 worktree `D:/github/my/E-Track`，被本次收口切到了
特性分支。处置是把它切回 `main` 再 `merge --ff-only`（未使用 reset / 强制覆盖）。另两个 worktree
持有 `p2-4-20260731` / `p2-5-20260801`，均非 main。切换前已确认无 tracked 改动；6 个刻意排除的
未跟踪文件全程保留。

## 7. 合并后 Governance 漂移声明（不得隐瞒）

回写看板会改变 `PLAN-OTA-EXEC.md` 字节 → Governance manifest 指纹变化 → P3-1-v2 合同内记录的
`governance.manifest_sha256` 与工作树不再匹配 → `validate_bundle.py` 对 P3-1-v2 转红。

这是**已冻结合同在收口回写后的正常状态**，不是缺陷，也不改判本轮 PASS：

- 同类现状实测：前一轮已收口的冻结合同 P2-6-v3 在本次收口前的工作树上**已经是红的**。
- 因此本次刻意分两步：先落**锚定提交**（看板保持冻结时字节，`1db4fc6` / merge `b36b868`
  在全新检出上复验为绿，见 §4），再由本次回写让 Governance 漂移。
- 合同的可复现性由锚定提交承载：任何人可 checkout `b36b868` 并复验 PASS。
- 不因此重算合同或升 v3：本轮验收已 PASS，为容纳收口回写而重新冻结属把流程面当结论面改。

回写后两条门禁的**实测**结果（不做美化）：

```text
$ python -B Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-1-v2.contract.json     --matrix docs/acceptance-contracts/P3-1-v2/P3-1-v2.evidence-matrix.json --repo-root .
ERROR: input manifest worktree length mismatch: PLAN-OTA-EXEC.md
ERROR: input manifest worktree SHA-256 mismatch: PLAN-OTA-EXEC.md
VALIDATION=FAIL errors=2
EXIT=1

$ python -B -m unittest tests.ota.test_acceptance_bundle
Ran 65 tests in 36.516s
OK
EXIT=0
```

两点须看清：

1. 转红的**全部**原因就是 Governance top_file `PLAN-OTA-EXEC.md` 的长度与 SHA-256 变了，
   `errors=2` 且再无其他条目——漂移范围精确等于本次回写，没有夹带任何产品或验收资产变化。
2. `tests/ota/test_acceptance_bundle.py` 65 项**仍全绿**。它是
   `.github/workflows/acceptance-governance.yml` 的门禁内容，因此本次回写不会打红 CI。

## 9. 看板回写的实际改动（3 处，`git diff --numstat` = `4  2`）

- P3-1 卡状态行：追加 `收口: Claude(P3-1 非实现非本轮验收收口会话) / 2026-09-02` 字段。
  状态取值仍为 `完成` —— 看板 §0 第 10 条把取值钉死为 `待办/进行中/阻塞/完成`，不自造 `已收口`。
- P3-1 卡证据行：`2026-09-02 未 commit/push;` → 收口结论（分支名、PR 号、两条门禁、闭环结果）
  + 本文件路径。
- §10 会话日志：按「最新在前」在表头后插入 1 条（该区为 bare LF，与既有条目一致）。

EOL 自检：CRLF 计数 705 保持不变，bare LF 239→241（恰为新增的 1 条目行 + 1 空行），
「内容相同仅行尾不同」的删加对 = 0，无 `edit-tool-normalizes-mixed-eol` 记载的整体规范化污染。

**看板内不含任何哈希**（含 commit SHA）：派工书 §九 字面要求「不得记录任何哈希」，commit SHA
也是哈希，故本次比 P2-6 先例更严——P2-6 曾把锚定 commit `9afd51e` 写进 §10 会话日志，本次
一律不写，改由看板记 PR 号与本文件路径，SHA 全部落在本文件 §1。追溯性不损失：PR #12 唯一确定
merge commit，本文件 §1 亦直接登记。机器自检确认新增行内无 ≥7 位十六进制串。
（证据行里的「产物SHA-256」是冻结时既有措辞，指笔记内含哈希，本身不是哈希值，非本次新增。）

## 8. 刻意未做

- **未改** `.github/workflows/firmware-build.yml`（Production profile 的 `top_file` 与
  `required_path`，改它会使 P3-1-v2 的 Production 指纹失效）。CI 未接入两套 BLE 测试的缺口已在
  冻结合同 `scope.excluded_by_freeze` 显式记录，并由 P3-6 卡承接、§9 已登记。
- **未动** P3-6 的 `dependency_state`（置 `SATISFIED` 会使其转 `DISPATCHABLE`，打红
  `tests/ota/test_acceptance_bundle.py` 内钉死的 `{P3-1,P3-2,P4-2}` 首批派单断言）；须与 P3-6
  派工书编写同批走治理变更。
- **未改** 任何产品源、验收资产字节或契约文件（`PLAN-OTA.md`、`docs/ota-binary-contracts.md`）。
- 临时产物全部落仓库内已忽略的 `.cache/p31-eol/`，无仓库外写入。
