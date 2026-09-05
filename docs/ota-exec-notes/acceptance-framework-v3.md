# 验收框架 v3：从工作树 manifest 到 git 对象冻结点

日期：2026-09-05
执行会话：Claude（初版）+ Codex（提交前复审与闭环补强），均未认领任务卡
授权：用户批准三层修法，并在提交前复审后授权继续实现与提交收口。

本笔记记录三层修法的动机、改动清单、实测证据与已知副作用。不含任何提交哈希，
冻结点索引统一在 `docs/acceptance-contracts/FREEZE-INDEX.md`。

## 1. 问题：跨轮输入身份与执行工作树混为一谈

v2 用自研 PowerShell 生成器 `Tools/provenance/source_manifest.ps1` 把每个 profile
的工作树字节（相对路径 + 长度 + 内容 SHA-256）冻结成 manifest，合同用
`manifest_sha256` 绑定它。它已经正确排除了 mtime、绝对 `RepoRoot`、HEAD 和证据目录；
真正造成脆性的因素是：

- **行尾**。`core.autocrlf=true` 下索引里的 LF 文本检出成 CRLF，字节数与哈希都变。
  仓库为此长出一份 200 多条的 `.gitattributes` `-text` 白名单，且必须"只增不改"。
- **收口回写**。看板 `PLAN-OTA-EXEC.md` 是 Governance profile 的 `top_files`，
  而每轮收口都必然回写看板 §10 会话日志 —— 于是两轮之间任何一行日志改动都会打红
  整个 Governance 组，使全部治理判据丧失复用资格。
- **工作区状态**。最终校验读取工作树而非冻结提交，profile 内未跟踪文件和磁盘字节
  会改变结果；同一 Git tree 在不同检出策略下也可能得到不同字节。

叠加的后果是：7 份已冻结包（P2-6-v1/v2/v3、P3-1-v2、P3-2-v1、P3-6-v1、P3-7-v1）
在 `main` 顶端复校都会红；其中既有看板和检出行尾噪声，也可能包含后续真实产品或验证
输入变化。正确动作不是把历史包套到当前产品，而是复校历史包自身，或用机器生成的
rerun plan 判断旧证据能否用于新 tree。历史上还出现过“看板记录哈希再绑定看板”的自指环。

## 2. 三层修法

### 层 1：把「一次性资产」写进规约（治理层）

- `AGENTS.md`「独立验收执行规约」重写第 3、6、7、8 条，新增第 9-12 条：
  - 实现与 harness 先提交再验收；执行 worktree 必须保持 profile clean；PR 只允许保留
    原提交 ID 的 merge/fast-forward，禁止 squash 与 rebase-merge。
  - 轮次核验器（`tests/ota/p*_verify_*.py`）是一次性资产；冻结包是不可变审计资产，
    可在 `bundle_commit` 自校验，但 PASS 只适用于其 `freeze_tree`。后续适用性由 rerun
    plan 判定，禁止为了让历史核验器在 `main` 顶端变绿而回改冻结字节。
  - 7 份 v2 冻结包不能用 `main` 顶端的 v3 校验器复校；应 checkout 到
    `FREEZE-INDEX.md` 登记的 `bundle_commit`，用该提交自带的校验器复校。
  - 新写核验器只断言长期事实或只读冻结证据（样板 `tests/ota/p3_7_verify_ci_evidence.py`，
    零 git 调用）；轮次专用脚本放 `docs/acceptance-contracts/<id>/tools/`，不放
    `tests/`，避免进入 Validation profile 后被后续卡的合法改动打红。
- 新建 `docs/acceptance-contracts/FREEZE-INDEX.md`：7 份包的 `bundle_commit` /
  `freeze_commit` / `freeze_tree` 登记表 + 复校方法。证据包先提交，索引行由后续提交追加；
  该文件不在任何 profile 内，所以不会要求一个提交记录自身 SHA。

### 层 2：把每轮必然回写的文件移出 profile

`Tools/provenance/manifest_profiles.json`：`PLAN-OTA-EXEC.md` 从 Governance 的
`top_files` 与 `required_paths` 中移除；`FREEZE-INDEX.md` 也不纳入（`docs/acceptance-contracts/`
只保留两份 template 的精确路径）。看板本身的权威性不变 —— 它由看板规则和 PR 审阅
约束，不需要靠 manifest 指纹守护。

### 层 3：输入组改为引用 git 对象（合同 v3）

- 合同 schema 升 `etrack-acceptance-contract-v3`，顶层新增 `freeze_commit`（被验实现
  所在提交）、`freeze_tree` 与 `profile_config_blob`。输入组只剩 `id` / `profile` /
  `category` 三个字段。
- 校验器用 Git 对象定义跨轮身份，并单独核对执行 worktree：
  - `cat-file -t` 判类型、`rev-parse --verify --quiet <commit>^{tree}` 核对
    `freeze_commit^{tree} == freeze_tree`；
  - 从每个 `freeze_tree` 读取并校验 profile 配置 blob，再用其 pathspec 执行
    `ls-tree -r -z --name-only`，避免当前 checkout 改写历史范围；
  - `diff-tree -r -z --name-only --no-renames --no-commit-id <prev_tree> <cur_tree>`
    判失效。所有返回路径的调用使用 `-z` 并显式带 `-c core.quotepath=false`（仓库有非
    ASCII 路径 `Tools/图标/**`），路径集按 UTF-8 字节序排序。
  - profile 定义变化时对应组失效；两 tree 不同又没有可读仓库时**拒绝判定**，不默认
    “未失效”；
  - 最终验收要求 `freeze_commit` 是执行 HEAD 的祖先、冻结 tree 到 HEAD 无 profile
    提交变化，并拒绝 profile 内 tracked 脏文件和未跟踪文件；正常 autocrlf 检出仍为 clean；
  - v2 合同被显式拒绝，错误信息指向 `FREEZE-INDEX.md`。
  - `--previous-repo-root` 参数删除（两轮 tree 在同一仓库内比较）。
- 删除 `Tools/provenance/source_manifest.ps1`（自研生成器）与 `Legacy` profile。
  `etrack-input-manifest-v2` 随之废除。`Tools/provenance/worktree_guard.ps1` 保留
  —— 它被 `Tools/jlink/jlink-common.ps1` dot-source，且写入守卫仍然需要。

跨轮判定只读 Git 对象，所以 mtime、检出行尾、绝对路径、换 worktree、证据目录位置和
profile 外提交不再制造失效噪声。执行门禁仍会有意打红真实脏输入和 profile 内未跟踪文件，
防止用冻结提交为另一份工作树生成的产物背书。

## 3. 改动清单

| 文件 | 改动 |
|---|---|
| `AGENTS.md` | 第 3/6/7/8 条重写，新增第 9-12 条 |
| `docs/acceptance-contracts/FREEZE-INDEX.md` | 新建：7 份包的 bundle/input 冻结点 + 复校方法 |
| `Tools/provenance/manifest_profiles.json` | 看板移出 Governance；删 Legacy profile |
| `Tools/provenance/source_manifest.ps1` | 删除 |
| `Tools/acceptance/validate_bundle.py` | 升 v3；冻结 profile 配置；补执行 worktree 门禁；删 `--previous-repo-root` |
| `docs/acceptance-contracts/template.contract.json` | schema v3 + 三个冻结对象字段；输入组瘦身 |
| `docs/acceptance-execution-contract.md` | v2 → v3（§1、§3、§5、§6、§8 重写） |
| `docs/ota-prompts/prompt-template-acceptance.md` | manifest 措辞 → 冻结点措辞 |
| `docs/ota-prompts/prompt-template-implementation.md` | "Governance manifest" → "Governance profile" |
| `.github/workflows/acceptance-governance.yml` | checkout 改为完整历史，供索引与祖先关系检查 |
| `tests/ota/test_acceptance_bundle.py` | manifest 用例改为对象、执行 worktree、索引与失效回归 |
| `tests/ota/test_p2_5_build_provenance.py` | 3 个 ps1 用例改写为 git tree 枚举用例 |

`.gitattributes` 里 `/Tools/provenance/source_manifest.ps1 -text` 成为指向已删文件的
死条目。按该文件自己的"只增不改"约束未删除；它对不存在的路径无任何作用。

## 4. 实测证据

### 4.1 profile 枚举与失效判定

改动前探针曾把 `git ls-files -c` 的结果称为“工作树文件集”；该命令会列出索引里仍存在、
但磁盘上已删除的路径，因此不能证明脏工作树与 tree 相等。现已把工作树辅助枚举改为只返回
磁盘上实际存在的文件，并增加“已删除索引项不得伪装成现存文件”的回归测试。

对象侧结论仍成立：P3-7-v1 到其收口 HEAD 只改变了 profile 外的看板，因此三个输入组均
未失效；P3-6-v1 之后确实发生过 Production、Validation、Governance 三类真实变化，三组
失效是正确结果，不能归为噪声。

### 4.2 本地测试（串行，两个文件分别独立进程）

```text
python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle
Ran 81 tests in 130.3s -- OK

python -X utf8 -B tests/ota/test_p2_5_build_provenance.py
Ran 11 tests in 8.6s -- OK

python -X utf8 -B tests/ota/test_ac5_ram_budget.py
Ran 3 tests -- OK

python -X utf8 -B tests/ota/test_f435_build_bootstrap.py
Ran 14 tests -- OK

python -X utf8 -B tests/ota/spec-probes/p2-6/run_all.py
通过 8/8 -- 全部探针与记录结论一致
```

必须串行：两个文件都在仓库根建 `.acceptance-*` / `.manifest-*` 临时目录，并发会互相
看见对方的目录而产生假红。

新增的鉴别力用例（均为正反成对）：

- `freeze_commit` / `freeze_tree` / `profile_config_blob` 对象缺失、类型错、关系不匹配、
  非 git 目录 → fail-closed；历史 tree 始终使用自身冻结的 profile 配置；
- 删掉一个 Validation `required_paths` → 报"缺必需路径"；删光 Governance 路径 →
  报"profile 为空"而不是列一串缺失；历史提交不受后续删除影响；
- fixture 仓库两次提交：改 Validation 输入只打红 Validation；修改 Production profile 定义
  同时打红 Production 与承载配置文件的 Validation；
- 只提交证据包目录不打红；冻结后改 Product、profile 内脏文件或未跟踪文件必须打红；
- 对象存在但不是执行 HEAD 祖先的提交必须打红；两 tree 不同又不给仓库必须 fail-closed；
- FREEZE-INDEX 的 7 行均校验 bundle/freeze 对象、tree 和祖先关系；治理 CI 使用完整历史；
- 真实仓库 `HEAD^{tree}` 覆盖三个 profile 的全部 `required_paths`；
- fixture 仓库上 tree 枚举与工作树枚举逐路径相等，且非 ASCII 路径
  `Tools/图标/README.md` 不因引号转义丢失。

### 4.3 已知噪声（既有，非本次引入）

`test_p2_5_build_provenance.py` 的三个 worktree guard 用例调用 PowerShell 并用
`text=True` 解码 stderr，中文 Windows 下 GBK 输出会在 reader 线程抛
`UnicodeDecodeError`。断言只看退出码与文件状态，测试结果不受影响。属既有代码，
本次未扩大范围去改。

## 5. 副作用（如实记录）

1. **7 份 v2 冻结包不能交给 main 顶端的 v3 校验器**，且从本次改动起错误更直接：v3 校验器
   显式拒绝 `etrack-acceptance-contract-v2` 并把调用者指向 `FREEZE-INDEX.md`。它们
   不再把“旧包是否自洽”和“旧证据能否用于当前产品”混为一件事。历史包仍按
   `FREEZE-INDEX.md` 的 `bundle_commit` 和该提交自带校验器复校。
2. **本次改动本身会打红 Validation 与 Governance 组**（改了校验器、profile 配置、
   执行合同、两份派单模板与两个测试文件）。这是正确的红：验收工具与治理规约确实变了。
3. 轮次核验器 `tests/ota/p*_verify_*.py` 未改动，也不需要改动 —— 它们是一次性资产。

## 6. 收口要求

- **治理 CI 必须由用户或主会话推 PR 触发**。本次改动落在
  `Tools/acceptance/**`、`Tools/provenance/**`、`docs/acceptance-contracts/**`、
  `tests/ota/test_acceptance_bundle.py`、`docs/ota-prompts/**`，全部在
  `.github/workflows/acceptance-governance.yml` 的 paths 内。按规约，本地测试通过
  **不能**代替 CI 接线。当前治理 workflow 已设置 `fetch-depth: 0`，并由测试核对索引中
  每个冻结提交、证据包提交和当前 HEAD 的祖先关系。
- 第一份 v3 合同将在下一张需要独立验收的卡上产生；本次未新建任何合同。

## 7. 复现命令

```powershell
# 只读探测：profile 规模、看板归属、跨轮失效判定
python -X utf8 -B .cache/probe/probe_v3_closeout.py

# 治理回归（必须串行）
python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle
python -X utf8 -B tests/ota/test_p2_5_build_provenance.py

# 冻结包复校（以 P3-7-v1 为例，命令模板见 FREEZE-INDEX.md）
git worktree add --detach .cache/freeze-check/wt-p3-7 <bundle_commit>
```

## 8. 后续规范补强

v3 的对象冻结解决了工作树字节和看板回写造成的跨轮假失败，但不能单独决定每轮执行
多少命令或硬件动作。后续合同必须为每项判据声明最小直接 profile 依赖，并按
“preflight → product → evidence”分阶段执行：工具/连接/RTT/WDT 准备失败不消耗产品配额，
harness 或证据修复只按 rerun plan 执行受影响命令，禁止无条件重跑整套宿主、构建和硬件流程。
调试域暂停 WDT 等必要准备动作可以存在，但必须在合同中写明地址、值、非持久性、恢复方式
和授权；“默认只读”不能被误解为禁止所有受控调试准备。

### 8.1 续作边界与复核结论（2026-09-05）

本轮承接未提交的规范补强，不改产品源码、历史冻结包或性能门槛，不认领 OTA 产品卡。
当前续作授权覆盖实现和本地验证；提交、推送与 PR 收口另行确认。

- 上次只落下多输入组的 `dependency_rationale` 校验，fixture 与配套回归未同步，不能沿用
  修改前的 83 项测试结果。本轮补齐合法、缺失、类型错误、重复依赖的正反用例。
- 现有 rerun plan 已按判据引用的 profile、外部输入、命令和产物选择重跑集合。本轮用真实
  Git fixture 验证其最小范围，不新增另一套路径依赖系统；同一 profile 内仍保守失效。
- 不得为减少重跑而漏报真实依赖：结果依赖 runner/探针时仍须声明 Validation，多个输入组
  用结构化理由说明用途，而不是把所有判据一律改为只依赖 Production。
- rerun plan 是失效计算，不是硬件操作或追加配额的授权。预检、观测、封包需要区分；必要
  的只读检查与证据校验不能被“只执行 required_commands”误禁，真实修复也不能被首次失败
  停止规则永久阻断。模板与看板同步引用这套执行口径。

### 8.2 本轮本地验证

测试串行执行，临时目录留在项目内，使用 `-B` 禁止 Python 字节码输出；Git 配置和模板、
TEMP/TMP/TMPDIR 指向 `.cache/acceptance-policy-20260905-01/`。Windows PowerShell
子进程的输出使用本机编码解码，避免旧测试的 UTF-8/GBK reader 线程异常。

| 命令 | 结果 |
|---|---|
| `python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle` | 94/94，121.196s，OK；`OTA_REQUIRE_SYMLINK_TEST=1`，无跳过 |
| `python -X utf8=0 -B tests/ota/test_p2_5_build_provenance.py` | 11/11，11.161s，OK |
| `python -X utf8 -B -m unittest tests.ota.test_ac5_ram_budget tests.ota.test_f435_build_bootstrap` | 17/17，0.054s，OK |
| Python AST、合同模板 JSON、`git diff --check` | 通过 |

三次最终测试共 122 项通过，0 失败、0 错误、0 跳过，测试输出无警告。Git 另有四个文本文件
的 LF/CRLF 转换提示，未修改行尾白名单。首次基线的缺理由失败与新环境 fixture 分类错误
均保留在本地日志，后者已修正为 environment-owned FAIL，未放宽校验器。

日志目录：`.cache/acceptance-policy-20260905-01/`，最终日志 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `governance.log` | `10A3E90911CBCE0FF8F62D2A6675B1D4626AB6BD105C9FD6D852047169AA85A2` |
| `provenance.log` | `CA1351A14D9CD6BCFEC6C4A2FD0699FA7D764550BB8D0DA979DEFA7E13177453` |
| `build-governance.log` | `264742471341356A9270FC8CB2664880B7971B476661AECE9EF8CD626BCCE1A7` |

本地回归不替代独立验收或治理 CI。本轮没有重编固件、执行真机操作或重跑未变的 Spec 探针；
尚未提交、推送或触发本批修改的远端 CI，不能宣告 PR 收口。

### 8.3 写入审计例外

八个原有未跟踪文件的 SHA-256 未变，旧 `.manifest-test-mzl4deqo` 未清理；测试创建的临时
fixture 已退出清理，保留的日志与配置在上述项目内缓存目录。但审计发现 PowerShell 自动
更新了两处项目外启动优化缓存，TEMP 与模块分析缓存设置未覆盖这类 .NET 启动数据。
以下为初次审计时的记录，不是不可变产物：

- `C:/Users/SU/AppData/Local/Microsoft/Windows/PowerShell/StartupProfileData-NonInteractive`：
  1196 字节，20:18 更新，来自 provenance 测试启动的 Windows PowerShell。
- `C:/Users/SU/AppData/Local/Microsoft/PowerShell/StartupProfileData-NonInteractive`：
  83692 字节，20:21 更新，来自终端 PowerShell 启动。

已向用户报告并停止后续 PowerShell 启动，改用 cmd 完成项目内记录；未删除、还原或移动
上述外部缓存。建议保留，若需清理必须取得针对准确路径的单独授权。

改用 cmd 后的只读复查又看到 Windows PowerShell 缓存于 21:12 更新为 1004 字节，PowerShell
缓存于 20:57 更新为 77236 字节；后续写入来源未确认，不能归因于本轮某条命令或声称缓存
已保持不变。本会话未再主动启动 PowerShell，也未对这两处路径执行清理或恢复。

### 8.4 后续提交授权

用户随后在当前会话明确授权提交、推送与 PR 合并；该授权不包含项目外缓存的清理或恢复。
本批只提交九个治理目标文件，八个原有未跟踪文件继续保留。主会话检查 Git 元数据与全局
hooks 后执行收口，保留 pre-commit 检查，使用显式提交信息。GitHub CLI 配置、缓存与临时
输出重定向到项目内，凭据仅在进程内读取，不写入仓库或日志。远端 CI 与 PR 结果将在合并前
补入本节；必须使用保留原提交 ID 的 merge，并在合并后同步持有 main 的主 worktree。
