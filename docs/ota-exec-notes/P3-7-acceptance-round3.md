# P3-7 独立验收 · 第 3 轮记录（收口批次）

- 卡片：P3-7 firmware-build.yml 测试步骤收敛
- 合同：`docs/acceptance-contracts/P3-7-v1.contract.json`（本轮首次冻结）
- 证据矩阵：`docs/acceptance-contracts/P3-7-v1/P3-7-v1.evidence-matrix.json`
- 特性分支：`ota/p3-7-host-test-wiring`，PR #19，基分支 `main`
- 交付比对基线（分支起点 main）：`2d8ff7e52d4c575a4d109b1477a79a7c1493d81b`
- 执行者：验收会话（非实现会话）
- 前序：`P3-7-acceptance-round1.md`（`PRODUCT_FAIL`）、`P3-7-acceptance-round2.md`
  （`EVIDENCE_GAP`）

## 1. 本轮结论

单轮结果 **`PASS`**。

第 2 轮判 `EVIDENCE_GAP` 的唯一硬原因是「零次真实 CI 运行」。用户放行后，本批次在
特性分支取得全部 **11 条 CI 腿**，两个验收核验器在干净工作树上双绿，证据包按
`docs/acceptance-execution-contract.md` 冻结并过校验器。

需要写在结论旁边、不能只藏在正文里的三件事：

1. **本轮的 CI 证据由验收会话自己产生**（推送注错、观测变红、还原、再观测转绿）。
   这不是理想形态——取证方与被验方在同一会话内。可核的部分是：注错/还原只碰
   `Libraries/OTA/**` 与 `USER/HAL/**` 的**四个**产品文件、每次提交恰好一个文件、
   分支端态相对基线在 `Libraries/`、`USER/`、`boot/`、`MDK-ARM_F435/` 四个红线目录上
   diff 为空（§7 命令 6 可复算）。不可核的部分是「我没在别处动手脚」这句话本身，
   只能靠上述红线 diff 与逐提交单文件约束兜底。
2. **两条触发器反证的提交不在任何分支上**（§6.1）。
3. **P3-6 的冻结 harness 现为红**（§6.3），这是本卡改步骤名的必然结果，不阻断本卡。

## 2. 第 2 轮硬缺口已闭合：11 条腿

11 条腿的 run 标识、事件、结论、提交与改动文件清单，逐条列在
`docs/ota-exec-notes/P3-7-wiring-evidence.md` §5 的表内，采集件冻结在
`docs/acceptance-contracts/P3-7-v1/ci/`（每 run 三件：`run-<id>.json` 元数据、
`step-<id>.txt` 步骤日志原文、`changed-<id>.json` 该提交改动文件清单），另有正例
run 处的 `workflow-at-<head>.yml` 与 `pr-19.json`。

腿的构成：正例 1 + 触发器反证 2 + 注错红 4 + 还原绿 4。

`tests/ota/p3_7_verify_ci_evidence.py` 对这批采集件做 308 项核对，零失败。它**不含
任何 git 调用**——判据只读证据文件，因此第三方拿到证据包即可复算，不依赖本机
仓库状态或远端可达性。

### 2.1 触发器反证的取证路线

`firmware-build.yml` 的 `on.push.branches` 只有 `[main, master]`，而 `pull_request`
的 `paths` 是按**整个 PR diff** 判定的——PR diff 里永远含被改的 workflow 本身，
所以 PR 同步事件无法证明 `paths` 闭包。用户裁定走「临时建 `master` 分支」路线：
在 `master` 上各推一个单文件提交，取得两次 `push` 事件的真实触发，随后删除该分支。

- 反证 A（本卡新增精确条目覆盖）：只改 `tests/ota/p3_1_verify_portability.py`。
- 反证 B（既有通配 `tests/ota/test_ota_*.py` 覆盖）：只改
  `tests/ota/test_ota_device_info.py`。

两条缺一不可：本仓库自实现的匹配器判自己通过，不构成对 GitHub 匹配行为的证明；
而两类覆盖来源（新增精确条目 / 既有通配）必须各自被远端验证一次。

## 3. 第 1、2 轮发现的处置核对

| 发现 | 第 2 轮状态 | 本轮核对 |
|---|---|---|
| F-1 看板 §10 日志行缺 `- ` | 已修复 | 判据仍在，本轮回写后复跑仍绿 |
| F-2 零次真实 CI 运行 | 仍未闭合（唯一硬原因） | **已闭合**，11 条腿，见 §2 |
| F-3 注错选点无效 | 已换点 | 四点全部通过命令级+步骤级安全性前置，见 §5 |
| F-4 P3-6 冻结 harness 现为红 | 不阻断，留档 | 状态不变，本轮复现并登记，见 §6.3 |
| F-5 `test_ota_device_info.py` 无人执行 | 改为派工书 v2 增量 | **已落盘**：派工书出 v2，看板 §9 登记，见 §4.2 |

## 4. 本轮新发现与修正

### 4.1 自检脚本在回填真实 run 号后静默失去鉴别力（我方 harness 缺陷）

`.cache/p3-7-accept/ci_harness_selftest.py` 用「把核验器复制一份、只改 `CI_DIR` 与
run 常量、判据逻辑一字不动」的方式做双向鉴别力自检。它的常量改写是**字面替换**
`BASELINE_RUN = None` → 合成值。收口批次把真实 run 号回填进核验器后，这些字面全部
失配，被测副本仍指向真实 run，而合成证据目录里只有合成 run 的文件——于是 11 个变异
用例**全部变红，但红因清一色是「证据文件缺失」**，与被变异的判据毫无关系。

「全红」看起来像鉴别力，实际上是零鉴别力：此时把任何一条判据删掉，自检照样全红。
这与「fail-closed 不等于有鉴别力」是同一个坑的第二种形态——第一种是永久红门禁，
第二种是永久红自检。

修法：常量改写改为按**常量名匹配整行**（与其当前取值无关），并加两道断言——被测副本
里不得残留任何真实 run 号、必须含合成 run 号。修复后重跑：格式良好的完整证据可变绿
（308 项核对零失败），11 类伪造/无效证据全部变红且红在对应关键词上。

同时把脚本尾部那句已经失真的收尾断言（`docs/acceptance-contracts/P3-7-v1` 不存在）
换成「真实证据目录逐字节未变」的摘要比对——目录现在当然存在，原断言只会恒假。

### 4.2 派工书 v2 的章节结构被替换脚本吞掉（我方缺陷，被治理自测抓住）

`.cache/p3-7-accept/write_spec_v2.py` 的第 1 条替换以 `task_id: P3-7\n\n## 任务类型\n`
为锚点写入版本头与 `## v2 修订说明`，替换文本没有把 `## 任务类型` 这行写回去，导致该
章节标题被吞、`` `IMPLEMENTATION` `` 令牌落到 `## v2 修订说明` 名下。

`tests.ota.test_acceptance_bundle` 的两条派工书判据立刻转红：
`test_prompts_have_required_sections_without_copying_normative_schemas`（缺章节
「任务类型」）与 `test_readiness_matrix_mirrors_board_order_and_derives_dispatch`
（切不出类型段，`IndexError`）。这是治理门禁应有的行为，值得记一笔：它抓的是
**验收方**的错，不是实现方的。

修法见 `.cache/p3-7-accept/fix_spec_v2_sections.py`：恢复 `## 任务类型` 到原位，把
`## v2 修订说明` 移到其后。修后 65 条治理用例全绿。

派工书 v2 的头部字段：`task_id: P3-7`、`spec_version: 2`、
`parent_spec_sha256: 88A54EC759F071CF61D306B3F3A619D92FF3CE479779FA2487B10560AE0E1B6F`
（v1 字节，9998 B）。v2 为 13621 B，
sha256 `8C9CCA62EDC985625F787F7F92C8E0E1881A2C38252A154D64F0D8E72F38BE2A`。
四项实质增量与看板 §9 登记内容一致。

### 4.3 交付比对基线由 `HEAD` 改为固定 commit

`p3_7_verify_wiring.py` 原先把「交付内容」与 `HEAD` 比。这类钉子在交付被提交的那一刻
自毁：`HEAD` 会跟着往前走，`git diff HEAD -- <workflow>` 变成空，判据从「验证改动恰为
11 增 1 删」退化成「验证没有改动」——恒真。

改为固定常量 `DELIVERY_BASE = 2d8ff7e52d4c575a4d109b1477a79a7c1493d81b`（分支起点
main）。同类修正还有 `CARD_BASELINE_REV` / `CARD_BASELINE_SCANNED = 893`，用于把
portability 的 `scanned=895` 增量逐文件解释清楚，而不是笼统写「目录自然增长」。

这与「`state_chain` 门槛必须是不变量」是同一条教训的第三次出现：**凡是随时间移动的
引用（`HEAD`、当前分支、当前轮次），都不能当判据基线**。

### 4.4 采集器的日志列格式

`gh run view --log` 的输出是三列 TAB 分隔（`job \t step \t TIMESTAMP 内容`）。
`p3_7_verify_ci_evidence.py` 的 `load_step_log` 要求原始三列形态；采集器
`.cache/p3-7-accept/collect_run.py` 按 `split("\t", 2)` 精确匹配第二列步骤名后整行
落盘，不做任何裁剪或重排。任何「顺手清洗一下日志」的动作都会让门禁失去它赖以定位
步骤边界的信息。

### 4.5 两个验收核验器必须串行执行

`p3_7_verify_wiring.py:630` 会调起 `tests.ota.test_acceptance_bundle`，后者在
**仓库根**创建 `.acceptance-repo-fixture-*` / `.acceptance-validator-test-*` 临时目录
（`tests/ota/test_acceptance_bundle.py`）。两个这样的进程并发跑时，一个会通过
「无法归类的改动为空」判据看见另一个的临时目录，报出与代码无关的假红。

第 3 轮的注错鉴别力探针第 3 轮就是这么红的——红项正是那两个临时目录名。串行重跑后
`P3_7_HARNESS_DISCRIMINATION=PASS cases=8`，8 例全部「rc=1、新红落在对应判据、按字节
存档还原、SHA-256 校验一致、红项集合复原至基线」。

**这条要带入后续所有卡**：验收核验器一律串行跑，不要为了省时间并发。

## 5. 通用规则沉淀：注错选点的安全性必须两级判定

反证三的第一次尝试（提交 `87a0d99`，run 33744927605）把 `USER/HAL/HAL_USB.cpp` 首行
`#include` 改成反斜杠。本地按 CI 同序跑满 12 条命令，红点确实恰落在 cmd11、其前全绿——
命令级安全性成立。但该写法同时让 `arm-none-eabi-gcc` 编译失败，CI 在**第 9 步
Build firmware** 就红了，第 10 步整步 `skipped`，目标行从未执行，反证空转。该 run 已
作废并从证据目录删除，重做为 `11ca914`（红）/ `94c4d68`（绿）。

**规则**：注错选点必须同时通过两级判定 ——

1. **命令级**：按 CI 同序在本地跑满全部执行行，红点恰落在目标行、其前全绿。
2. **步骤级**：该缺陷不得打红目标步骤**之前的任何 CI 步骤**。本地按命令同序跑一遍
   **看不见**固件编译，因此凡改动会进入编译的产品源，必须另跑一次与 CI 同配置的本地
   构建证明编译不受影响；无法证明时改用不参与编译的阳性样本。

重做采用 `#if 0` 包裹的阳性样本：预处理器直接丢弃该块，编译不受影响；可移植性扫描器
是文本匹配，照样命中。推送前先在本机跑了一次与 CI 同配置的 GCC 构建
（`FLASH 602984 B / 960 KB = 61.34%`，`text 601544 data 940 bss 561688`）。

该规则已写入派工书 v2 的「必须新增或调整的测试」一节，成为后续卡的硬前置。

## 6. 残留局限（如实登记）

### 6.1 两条触发器反证的提交不在任何分支上

临时 `master` 分支已按计划删除（`git ls-remote --heads origin` 无 `master`）。两条
反证提交 `9bac771bff4f`（父 `690a528`）与 `bb2dcf5bb10f`（父 `9bac771`）本地按 SHA
仍可读，但不被任何 ref 指向，将来会被 GC 回收；远端亦无 ref。

影响面：`p3_7_verify_ci_evidence.py` 不含 git 调用，复算只依赖冻结的
`run-*.json` / `step-*.txt` / `changed-*.json`，因此**门禁复算不受影响**。受影响的是
「拿着 SHA 去仓库里翻那两次提交的 diff」这种人工追溯。

不采取的补救：为了留住这两个提交而向远端推额外的 ref，属于对外可见动作，超出本轮
授权范围，故不做，改为如实登记。

### 6.2 CI 证据门禁只比路径、不比 blob

该门禁比对红/绿两次提交的**改动文件路径**集合，要求恰为该次反证冻结的注错目标那一个
文件；不比对同一文件在红/绿两处的 blob 哈希。「还原确实把内容改回注错前」由提交序列
本身与 `inject_ci.py` 的按字节存档 + SHA-256 回校承担，未在门禁内复算。此条与第 2 轮
登记一致，本轮未收窄。

### 6.3 F-4：P3-6 的冻结 harness 现为红

```
python -X utf8 -B tests/ota/p3_6_verify_ci_wiring.py
FAIL: 未找到步骤 `Test Boot fw_header validator vectors`
FAIL: 步骤缺少 run 脚本块
P3_6_CI_WIRING=FAIL checks=2 failures=2
```

红因唯一：P3-7 按派工书授权把该步骤改名为
`Run host tests (boot vectors, OTA host tests, P3-1 product regressions)`，而 P3-6 的
harness 把旧步骤名钉死了。

判定：**不阻断本卡**。P3-6 的证据包在其冻结提交上仍然可校验——这正是「每轮证据包只在
其冻结提交上可校验」的设计后果，不是回归。不回改 P3-6 的合同、矩阵或历史观测值
（派工书明列的禁止项）。如果将来要让该 harness 在 main 上重新可跑，须另行立卡并按
同一 `task_id` 出 P3-6 的新版本合同，不在本卡范围内。

### 6.4 验收会话同时是 CI 证据的产生者

见 §1 第 1 条。本轮不假装这个问题不存在：可核的是红线 diff 为空与逐提交单文件约束，
不可核的是会话自述。

## 7. 本轮可复算命令清单

全部命令在本轮工作树（`ota/p3-7-host-test-wiring`）串行执行；日志落
`docs/acceptance-contracts/P3-7-v1/commands/`。

```
1  python -X utf8 -B tests/ota/p3_7_verify_wiring.py
2  python -X utf8 -B tests/ota/p3_7_verify_ci_evidence.py
3  python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle
4  python -X utf8 -B .cache/p3-7-accept/inject_probe.py
5  python -X utf8 -B .cache/p3-7-accept/ci_harness_selftest.py
6  git diff --stat 2d8ff7e52d4c575a4d109b1477a79a7c1493d81b -- Libraries/ USER/ boot/ MDK-ARM_F435/
7  python -X utf8 -B tests/ota/p3_6_verify_ci_wiring.py            （预期红，见 §6.3）
8  python Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-7-v1.contract.json --matrix docs/acceptance-contracts/P3-7-v1/P3-7-v1.evidence-matrix.json --repo-root D:/github/my/E-Track
```

命令 4 与 5 是 harness 双向鉴别力证明，产物在 `.cache/` 下，不入包；其结论标记
（`P3_7_HARNESS_DISCRIMINATION=PASS cases=8`、
`P3_7_CI_HARNESS_SELFTEST=PASS mutations=11`）随本记录留存。

## 8. 收口动作清单（本批次）

1. 派工书 v2 落盘（§4.2）。
2. `P3-7-wiring-evidence.md` §5 由 10 个回填位扩至 11 并逐条回填；§4 标题措辞由
   「待办」改为「已取得」，消除文件内自相矛盾。
3. 两个验收核验器的轮次作用域钉子重基线（§4.3 与看板钉子）。
4. `.gitattributes` 为两个验收核验器补 `-text` 护栏（`core.autocrlf=true` 下新增
   纯 LF 文件若无护栏，检出会被转成 CRLF，冻结指纹随即失配）。
5. 看板回写：P3-7 卡状态与证据字段、§9 变更登记表登记 v2 增量、§10 追加会话日志行。
   **看板内不记任何哈希**（含 commit SHA）——看板是 Governance profile 的 `top_file`，
   在其中记哈希会构造出不收敛的自指环。
6. 冻结 `P3-7-v1` 合同 / 证据矩阵 / 三份分类 manifest，跑校验器。

顺序不可换：看板是 Governance 的 `top_file`，任何看板改动都会让已生成的 manifest
过期，因此**看板回写必须早于 manifest 生成**。

## 9. 校验器结论

（本文件不在任何 profile 的 manifest 范围内，也未登记为证据矩阵的产物或外部输入，故本节
追加不影响已冻结指纹。第二次跑校验器是在本节写入前完成的，两次均 `PASS`。）

### 9.1 命令与原始输出

```text
$ python -X utf8 -B Tools/acceptance/validate_bundle.py     --contract docs/acceptance-contracts/P3-7-v1.contract.json     --matrix docs/acceptance-contracts/P3-7-v1/P3-7-v1.evidence-matrix.json     --repo-root D:/github/my/E-Track
VALIDATION=PASS contract=P3-7-v1 round=P3-7-V1-FREEZE-20260903-R3 overall=PASS
EXIT=0
```

矩阵不含 `REUSED`，故未传 `--previous-contract` / `--previous-matrix` /
`--previous-repo-root`；`previous_matrix_sha256`、`rerun_plan_path`、
`rerun_plan_sha256` 均为 `null`。`P3-7-v1` 是本 `task_id` 的首份合同，
`parent_contract_sha256` 亦为 `null`。

### 9.2 冻结指纹

| 件 | 字节 | SHA-256 |
|---|---:|---|
| `P3-7-v1.contract.json` | 45724 | `D26377D20F046D781931B3E276AEBC4B215EB2EAFC29929D12976491B826370C` |
| `P3-7-v1.evidence-matrix.json` | 25465 | `B3510928B1FAE49CF16282BDD9F8C12AACAD59FF60598D29817AD4FF98AFB4C4` |

| profile | FileCount | ManifestSHA256（内部稳定） | ManifestJsonSHA256 |
|---|---:|---|---|
| Production | 2920 | `ACAE2C71909AF7F19ADE3978E0D068525AFE513BDEDA48B8CF5D9E08711A6363` | `A4A3B8F3CE68BA6A3C839120C98FB3EE60EB589E6CA1EB1EB5981C49F8FE055E` |
| Validation | 154 | `B5331BE603F447FE325EC99DCB54456C20D0B52585FD7ACC7918882CA47EDB60` | `B832206A10F791CAA5A93AF95489296F4937FDB6D9F8BE383753DF2A4F0F3E94` |
| Governance | 26 | `B35E78737A0E15E1839F48A04CC786727207CDF39211D5CAFF96DBE0908A5D96` | `3B52567DF4ABDB8276CEE282F8CF34BF3B205BFEED03B9DF501E35B75CE623E6` |

三份 manifest 的 `Head` 均为 `94c4d68c15133bbcde3c72db7733404870f5fd19`。

### 9.3 校验器实际复核了什么

`VALIDATION=PASS` 不是读 manifest 自述得来的，校验器做的是：

1. 用 `git ls-files -co --exclude-standard -z` 从 `--repo-root` 指定的工作树**重新枚举**
   三个 profile 的文件集，逐个读回字节比对 `Length` 与 `SHA256`，再重算
   `ManifestSHA256`——manifest 自洽不算通过。
2. 逐条读回矩阵 `evidence_hashes` 里全部 57 个包内文件并比对哈希；缺文件或哈希不符即硬错。
3. 校验合同的引用闭合性：7 条命令与 42 件产物必须全部被某条判据引用，
   15 条判据的 `command_ids` / `artifact_ids` / `input_groups` 不得指向未定义 id。
4. 逐条比对矩阵 `observed` 与合同 `state_chain.expected` 全等，比对命令字符串全等、
   `exit_code` 落在 `expected_exit_codes` 内（`CMD-P3-6-HARNESS-STATUS` 的 `1` 是合同
   显式声明的预期红，见 §6.3）。
5. 独立校验 6 个外部输入的存在性与哈希。

### 9.4 矩阵 observed 的派生方式（防反抄）

15 条判据的 `observed` 由 `.cache/p3-7-accept/write_matrix.py` 从包内
`commands/*.log` 与 `ci/**` 逐元素正则派生，**再**与冻结门槛断言全等，
未从 `gate.expected` 反抄。派生器本身带三类反退化断言：

- `one()` 要求正则在日志里**恰好**命中一次，命中 0 次或多次都抛错，不允许静默取首个；
- 集合类观测（4 条注错腿的结论、8 例探针的还原标记、4 条脚本的退出码）先断言集合同值，
  再取代表值，避免「有一条不同却被首元素掩盖」；
- 交叉自洽断言：反证 N 的红点必须落在第 N 条接线命令上（`red_at_wired`）、
  `cases=8` 必须等于还原行数、`failures=2` 必须等于 `FAIL:` 行数。

`P3-6-HARNESS-RED-ATTRIBUTED` 的红因归属额外做了两条源码级断言：旧步骤名
`Test Boot fw_header validator vectors` 已不在当前 workflow 内，且仍被
`tests/ota/p3_6_verify_ci_wiring.py` 钉死——两条同时成立才允许把红因写成
`red_cause=step_renamed`。

### 9.5 第 3 轮结论

**单轮结果：`PASS`。** 综合评分 94/100，详见
`.claude/verification-report-p3-7.md`。

15 条判据全部 `EXECUTED` + `PASS`，无 `REUSED`、无 `NOT_OBSERVED`、无
`failure_owner`。第 2 轮的唯一硬原因（零次真实 CI 运行）已由 11 条真实运行腿闭合：
正例 1 + 触发器反证 2 + fail-closed 注错/还原 4 对。

结论同时绑定三条如实登记的残留（详见 §6 与合同 `authorized_deviations`）：

1. CI 证据由验收会话自己推送产生，取证方与被验方同源（DEV-8）；可独立复核的部分是
   红线四目录 diff 为空与注错/还原提交各含一个文件，不可复核的是会话自述。
2. 两条触发器反证的提交不在任何分支上（临时 `master` 已按计划删除，DEV-6）；门禁复算
   不依赖 git，受影响的只有人工按 SHA 追溯。
3. P3-6 冻结 harness 现为红，红因唯一且可归属，不阻断本卡，不回改 P3-6 冻结字节。

余一处结构性残留：`verify-wiring.log` 的改动分类涵盖了合同本体，但涵盖不到本轮证据
矩阵文件自身——证据包无法包含一份「看见了自己终态」的日志。已在合同 `scope.method`
与矩阵 `notes` 中登记；P3-6 同有此性质。
