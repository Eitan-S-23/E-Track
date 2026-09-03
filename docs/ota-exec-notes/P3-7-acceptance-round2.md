# P3-7 独立验收 · 第 2 轮（派工书 v2 增量）

- 轮次: `P3-7-V2-ROUND2-20260903-01`
- 会话: Claude（非实现方独立验收会话；本会话只做立卡、冻结派工书与验收，未参与实现）
- 日期: 2026-09-03
- 被验对象: `main` HEAD `2d8ff7e52d4c575a4d109b1477a79a7c1493d81b` + 实现方未提交工作树改动
- 被验产物: `.github/workflows/firmware-build.yml`
  （22045 B，`sha256=A43A002D298875E0EA4F2ACE374DC6F78B035E65B2E80A0C569C05E160DC8F77`，
  相对 HEAD `11 insertions(+), 1 deletion(-)`）
- 判定依据: 冻结派工书 `docs/ota-prompts/prompt-P3-7-implementation.md`
  （9998 B，`sha256=88A54EC759F071CF61D306B3F3A619D92FF3CE479779FA2487B10560AE0E1B6F`）
  的「完成判据」，加上本会话以对话提示词下发、尚未落成文件的 v2 增量（见 §6，属我方流程偏差）。

## 1. 本轮结论

**`EVIDENCE_GAP`（不通过；与第 1 轮同因，非产品实现错）。**

v2 增量（第 4 条接线）经独立复算全部成立，第 1 轮唯一的产品面缺陷 F-1 已修复。
卡不能收口的唯一硬原因仍是**零次真实 CI 运行证据**，而这条要求在冻结派工书里明文
不可绕：

> 禁止用「本地执行通过」或「workflow 文本 diff」替代真实 CI 运行日志。

实现方对此判断一致，其证据笔记 §4/§5 如实声明「需主会话推送后补齐」并留了回填位。
这不是隐瞒，缺口成因是我方派工书的结构缺陷（第 1 轮 §7 已自认：判据要求了实现方
按看板 §0 规则 8 在结构上被禁止产出的证据）。

本轮另有两项须由我方承担的更正：一处第 1 轮的**错误裁定**（§4），一处 CI 取证
**要求上调**（§5，从 10 条腿加到 11 条）。两者都不是实现方的缺陷。

## 2. 第 1 轮发现的处置核对

| 编号 | 第 1 轮判定 | 本轮实测 |
|---|---|---|
| F-1 看板 §10 日志行缺 `- ` | 产品面缺陷，阻断收口 | **已修复**。§10 全部 183 行逐行核对，零遗漏 |
| F-2 零次真实 CI 运行 | 缺口的唯一硬原因 | **仍未闭合**，`P3_7_CI_EVIDENCE=FAIL reason=ci_dir_missing` |
| F-3 三处注错选点两处无效 | 须换点 | 实现方已换点；**但我方给的替代点之一同样无效**，见 §4 |
| F-4 P3-6 冻结 harness 现为红 | 不阻断，留档 | 状态不变，无新增影响 |
| F-5 `test_ota_device_info.py` 无人执行 | 建议立新卡 | **改为派工书 v2 增量**（用户裁定：另立新卡使计划臃肿），见 §3 |

第 1 轮记录头部的日期笔误（写成 2026-09-04）本轮已更正为 2026-09-03，轮次 ID 同步
改为 `P3-7-V1-ROUND1-20260903-01`。该文件当时未被任何 manifest 绑定，更正不影响已冻结件。

## 3. v2 增量的独立复算

全部命令由本会话在同一工作树重跑，不采信实现方的观测转述。

| 命令 | 退出码 | 观测 |
|---|---:|---|
| `python -X utf8 -B tests/ota/p3_7_verify_wiring.py` | 0 | `P3_7_WIRING=PASS checks=163 failures=0` |
| `python -X utf8 -B tests/ota/test_ota_device_info.py` | 0 | `P3_2_OTA_DEVICE_INFO checks=114 failures=0` / `_ALL=PASS` |
| `python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle` | 0 | `Ran 65 tests` / `OK` |
| `python -X utf8 -B .cache/p3-7-accept/inject_probe.py` | 0 | `P3_7_HARNESS_DISCRIMINATION=PASS cases=8` |
| `python -X utf8 -B .cache/p3-7-accept/ci_harness_selftest.py` | 0 | `P3_7_CI_HARNESS_SELFTEST=PASS mutations=11` |
| `python -X utf8 -B tests/ota/p3_7_verify_ci_evidence.py` | 1 | `FAIL ... reason=ci_dir_missing`（即 §1 缺口） |

### 3.1 workflow 改动

真实 diff 为 `11 1`，加 `-w` 复算同为 `11/1`（不存在仅空白差异的配对），裸 LF 计数
恰增 10。与实现方自述一致。第 4 条接线的落法经复算正确：

- 唯一新增执行行 `python3 tests/ota/test_ota_device_info.py`，追加在
  `p3_1_verify_portability.py` 之后、同一 `set -euo pipefail` 块内，裸执行无任何削弱子句；
- **`paths` 一行未动**。两份列表仍各 18 条且逐项相等；`test_ota_device_info.py` 被既有
  通配 `tests/ota/test_ota_*.py` 覆盖，覆盖关系由核验器**实算**（非声明）；
- 互镜判据保持：新增的三条精确条目仍不命中 5 个不接入脚本。

「不新增冗余精确条目」不是可有可无的洁癖——它使本次增量的 `paths` 改动为零，
从而不触碰 `P3-1-v2` 与 `P3-6-v1` 两份冻结合同按路径绑定的那 8 个脚本路径。

### 3.2 看板

`git diff --numstat HEAD` 为 `4 2`；改动为第 648 行（状态/认领/更新）、第 657 行
（证据字段）与 §10 新增的两行（v1/v2 各一）。CRLF 计数恰增 2，裸 LF 不变，与
「只用 Python 字节编辑」自述吻合。四行新增内容零哈希类记号（`20260903` 等纯数字
日期不构成哈希）。看板作为 Governance profile 的 `top_file`，记哈希会形成不收敛的
自指环，这条红线本轮未被触碰。

## 4. 我方第 1 轮一处错误裁定的更正

第 1 轮 §3 F-3 的替代选点表中，**「合同对齐 / 命令位 9 / `OTA_BLE_LEN_ACK_OTHER`
9u→8u」这一行是错的**，须作废。

实测：`Libraries/OTA/ota_ble_session.c` 用该常量作数组维度，改小后
`-Werror=array-bounds` 在**第 8 条** `test_ota_ble_session.py` 的编译期就触发
（`ota_ble_session.c:73:12: error: array subscript 8 is above array bounds of 'uint8_t[8]'`），
步骤在那里短路，第 9-12 行从未执行——这正是我在同一节里指控实现方原选点犯的那个错，
我自己又犯了一次。

根因是我方探针 `.cache/p3-7-accept/classify_symbols.py` 只扫了 `tests/**/*.{c,h,py}`
里的**文本引用**，漏掉产品翻译单元。**通用规则（须带入后续所有卡）**：注错选点的
安全性必须按前置命令的**传递编译集**判定，不能只扫测试目录的文本引用。

实现方按 12 条同序预演逐点实测后改用 `OTA_BLE_LEN_ACK_BEGIN` 10u→11u，红点精确落在
第 9 条（`[DRIFT] §5.6 ACK_BEGIN 10B: 契约=10 实现=11`）。本会话独立复跑该选点确认成立。
另需指出：派工书第 111 行把「三处注入缺陷的具体选点」明确划为实现方可自行决定，
我第 1 轮以表格形式给出选点已属越权指导，本次被推翻是应有结果。

四处定案选点（均经本会话独立复算，每次按 CI 同序跑满 12 条）：

| 命令位 | 判据 | 选点 |
|---:|---|---|
| 9 | 合同对齐 | `Libraries/OTA/ota_ble_frame.h` `OTA_BLE_LEN_ACK_BEGIN` 10u→11u |
| 10 | 文本隔离 | `USER/HAL/HAL_Bluetooth.cpp` sink 守卫置 NULL |
| 11 | 可移植性 | `USER/HAL/HAL_USB.cpp:1` 插反斜杠 `#include` |
| 12 | 设备身份 | `Libraries/OTA/ota_device_info.c` `k_ota_device_model` 首字符 `'E'`→`'F'` |

## 5. CI 取证要求上调：10 条腿 → 11 条（我方新增要求，非实现方缺陷）

我此前告诉用户 v2 使 CI 腿数由 8 增至 10。**这个数字要更正为 11。**

多出来的一条是「触发器反证 B」：只改 `tests/ota/test_ota_device_info.py`（仅注释）
推一次，确认 workflow 被触发。理由是本轮才想清楚的——cmd12 的 `paths` 覆盖不来自
本卡新增条目，而来自既有通配 `tests/ota/test_ota_*.py`；而「该通配覆盖该文件」这件事
目前只由**本仓库自实现的 `glob_match`** 断言，不是 GitHub 的匹配实现。自己实现的
匹配器判自己通过，不构成对远端行为的证明。

代价如实说：多一次纯注释推送与一次 CI 运行。实现方证据笔记 §5 只留了 10 个回填位，
是照我先前的说法写的，需扩到 11 位——这是我的要求变更，不记为其缺陷。

11 条腿：正例 1 + 触发器反证 A（新增精确条目）1 + 触发器反证 B（既有通配）1 +
四次注错红 4 + 四次还原绿 4。

## 6. 我方流程偏差自认

看板 §0 规则 11 要求派工前先冻结派工书文件。**v2 增量是以对话提示词下发的，
`docs/ota-prompts/prompt-P3-7-implementation.md` 至今仍是 v1 字节（9998 B，
上列 sha256），文件层面的 v2 修订与看板 §9 变更登记均未落盘。** 实现方是照口头
提示词做的，交付无偏差；偏差在我。

本轮不就地补写的理由是可核的：补写会改看板与派工书字节，而当前 harness 的三项看板
钉子（diff `4 2`、CRLF +2、§10 行数）正是用来证明「实现方只改了这 4 行、无夹带」的，
现在改会把本轮被验状态搅浑。修复安排在收口批次（看板本来就要再改一次），届时：

1. 派工书按同一 `task_id` 出 v2，版本加一，用 `parent_contract_sha256` 绑 v1；
2. 看板 §9 变更登记表登记该增量（不记哈希）；
3. 同批更新 harness 的看板钉子基线。

顺带记一笔教训：上述三项钉子是轮次作用域的，会随任何一次看板回写失效——与
「state_chain 门槛必须是不变量」是同一类问题，只是这里的钉子服务于单轮取证，
不是长期门槛，故保留但须显式标注作用域。

## 7. harness 双向鉴别力（v2 复核）

fail-closed 只保证「没证据必红」，不保证有鉴别力。两个方向本轮都对 v2 重测：

- `inject_probe.py`：对 workflow 做 **8** 处单点注错，每次 rc=1、新红落在对应判据、
  按字节存档还原并以 SHA-256 校验、红项集合复原至基线。v1 的 I1-I5 之外，本轮新增
  三例专打 v2 判据：I6 删第 4 条执行行（新红 8）、I7 只删 push 侧的既有通配
  （新红 12，命中「既有通配仍在两份 paths 内」）、I8 为已被通配覆盖的脚本加冗余
  精确条目（新红 6，命中「冗余精确条目」）。没有这三例，v2 的新判据等于没被证明过。
- `ci_harness_selftest.py`：用合成的格式良好证据驱动 `p3_7_verify_ci_evidence.py`
  能变绿（308 项核对零失败，证明它不是永久红），再施加 **11** 类伪造/无效证据全部
  变红，含 M2「无效注错选点」（红运行缺前置标记）、M8「还原绿改的不是注错目标」、
  M9「同一 run 充当多条腿」、M11「触发器反证 B 改的是精确条目脚本」。自检临时件
  全部清理，`docs/` 下零落盘。

### 7.1 CI 证据门禁本轮的加强

`tests/ota/p3_7_verify_ci_evidence.py` 为 v2 重写，除腿数外有三处实质加强：

- **cmd12 的红形态与前三条不同**。`test_ota_device_info.py` 失败时**不打印 `=FAIL`
  汇总行**（C 用例输出 `failures>0` 返回 1，Python 侧 `check=True` 抛出，`_ALL=PASS`
  不再出现）。若照抄前三条的 `<PREFIX>=FAIL` 写法，该腿会成为恒真的空转判据。现按
  「`failures` 非零 + 存在 `FAIL: ` 明细 + `_ALL=PASS` 缺席」三条同时成立构造。
- **红绿因果归属**。每个红/绿 run 绑定其提交的改动文件清单
  （`changed-<run_id>.json`），必须恰为该次反证冻结的注错目标那一个文件，否则红因
  无法归属到注错。
- **正例范围**。正例提交须含被改的 workflow，且不得触碰 `Libraries/`、`USER/`、
  `boot/`、`MDK-ARM_F435/` 任一产品红线目录。

残留局限（如实登记）：该门禁只比对改动文件的**路径**集合，不比对同一文件在红/绿
两次提交处的 blob 哈希，「还原确实把内容改回注错前」由提交序列本身承担，未在本机复算。

## 8. 合同冻结与证据包仍推迟（理由不变）

Governance profile 绑定 `PLAN-OTA-EXEC.md` 字节，而看板必然还要再变（§6 的 §9 登记 +
验收回写）。先生成即保证整批重做。按「看板回写早于 manifest 生成」的既定顺序，合同与
包在 **CI 证据齐备的那一批次**一次性冻结并过 `Tools/acceptance/validate_bundle.py`。

`EVIDENCE_GAP` 按规约不属于必须绑定产物的结果类别（那是 PASS 与产品/harness FAIL 的
要求），故本轮不存在「该绑产物而未绑」的问题。

## 9. 收口条件（更新）

1. 用户放行推送后，在特性分支 `ota/p3-7-host-test-wiring` 取 **11** 次 CI 运行
   （见 §5）。每次注错前先在本地按 CI 同序跑满 12 条命令预检。
2. `gh` 采集件冻结进 `docs/acceptance-contracts/P3-7-v1/ci/`：每 run 的
   `run-<id>.json`、`step-<id>.txt`、`changed-<id>.json`，正例 run 处的
   `workflow-at-<head>.yml`，以及 `pr-<n>.json`。
3. 回填 `p3_7_verify_ci_evidence.py` 的 run 标识常量并跑到绿。
4. `P3-7-wiring-evidence.md` §5 回填位由 10 扩至 11。
5. 补做 §6 的三件事（派工书 v2、§9 登记、harness 看板钉子重基线）。
6. 验收回写看板 + §10 追加一行（不记任何哈希）。
7. 冻结 `P3-7-v1` 合同 / 证据矩阵 / 三份 manifest，跑校验器，出第 3 轮结论。

## 10. 本轮可复算命令清单

```
python -X utf8 -B tests/ota/p3_7_verify_wiring.py
python -X utf8 -B tests/ota/p3_7_verify_ci_evidence.py
python -X utf8 -B tests/ota/test_ota_device_info.py
python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle
python -X utf8 -B .cache/p3-7-accept/inject_probe.py
python -X utf8 -B .cache/p3-7-accept/ci_harness_selftest.py
python -X utf8 -B tests/ota/p3_6_verify_ci_wiring.py     # 预期红，见第 1 轮 F-4
```
