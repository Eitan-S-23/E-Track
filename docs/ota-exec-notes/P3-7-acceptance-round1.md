# P3-7 独立验收 · 第 1 轮

- 轮次: `P3-7-V1-ROUND1-20260903-01`
- 会话: Claude（非实现方独立验收会话；本会话此前只做立卡与冻结派工书，未参与本卡实现）
- 日期: 2026-09-03
- 被验对象: `main` HEAD `2d8ff7e52d4c575a4d109b1477a79a7c1493d81b` + 实现方未提交工作树改动
- 被验产物: `.github/workflows/firmware-build.yml`
  （21993 B，`sha256=5C81470DAA93B75041854AFF739EB6189244C233F5D61F3AB7055B87066E2B54`，
  相对 HEAD `10 insertions(+), 1 deletion(-)`）
- 判定依据: 冻结派工书 `docs/ota-prompts/prompt-P3-7-implementation.md` 的「完成判据」
  与看板 §6 P3-7 卡验收字段。二者均为已入库的版本化冻结件，非本轮临时拟定。

## 1. 本轮结论

**`EVIDENCE_GAP`（不通过，但不是产品实现错）。**

接线本身经独立复算全部成立；卡不能收口的唯一硬原因是**零次真实 CI 运行证据**，
而派工书完成判据对此有明文且不可绕的要求：

> 至少一次真实 CI 运行日志显示三条脚本的实际执行输出与结论标记……触发器反证与
> 三次 fail-closed 反证完整，run 标识、提交 SHA 与关键日志片段均已留证。
> **禁止用「本地执行通过」或「workflow 文本 diff」替代真实 CI 运行日志。**

实现方对此判断一致（其证据笔记 §4/§5 已如实声明「需主会话推送后补齐」并留好回填位），
这不是隐瞒。缺口的成因见 §7——是我方派工书的结构缺陷，不是实现方的执行缺陷。

另有一项确认的产品面缺陷（§3 F-1，看板列表标记）须一并修复后才具备收口条件。

## 2. 已独立复算通过的部分

全部命令由本会话在同一工作树重跑，不采信实现方的观测转述。

| 命令 | 退出码 | 观测 |
|---|---:|---|
| `python -X utf8 -B tests/ota/p3_1_verify_contract_alignment.py` | 0 | `P3_1_CONTRACT_ALIGNMENT=PASS drift=0 checks=47` |
| `python -X utf8 -B tests/ota/p3_1_verify_text_isolation.py` | 0 | `P3_1_TEXT_ISOLATION=PASS cases=3 transparent=0 trace_points=1 sink_guard=True` |
| `python -X utf8 -B tests/ota/p3_1_verify_portability.py` | 0 | `P3_1_PORTABILITY=PASS scanned=895 control_hits=1 live_hits=0 new_src_hits=0` |
| `python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle` | 0 | `Ran 65 tests` / `OK` |
| `python -X utf8 -B tests/ota/p3_7_verify_wiring.py` | 1 | `P3_7_WIRING=FAIL checks=149 failures=1`（唯一红项 = F-1） |
| `python -X utf8 -B .cache/p3-7-accept/inject_probe.py` | 0 | `P3_7_HARNESS_DISCRIMINATION=PASS cases=5` |
| `python -X utf8 -B .cache/p3-7-accept/ci_harness_selftest.py` | 0 | `P3_7_CI_HARNESS_SELFTEST=PASS mutations=6` |
| `python -X utf8 -B tests/ota/p3_7_verify_ci_evidence.py` | 1 | `P3_7_CI_EVIDENCE=FAIL ... reason=ci_dir_missing`（即 §1 缺口） |

`p3_7_verify_wiring.py` 的 149 项核对覆盖：命令序列逐行全等（守卫 1 + 既有 8 +
新增 3）、两份 `paths` 逐项相等、执行行闭包、**新增条目不覆盖 5 个不接入脚本**
（互镜）、顶层 `name` 与 `jobs.build.name` 字节未动、步骤无
`continue-on-error`/`if`、全文无 fail-closed 削弱写法、改动文件集合不越红线、
以及三条脚本的实际执行与标记复算。

### 2.1 对实现方一处观测措辞的更正（不影响结论）

实现方把 `portability` 的 `scanned` 由立卡基线 893 变为 895 记为「目录自然增长」。
实测原因是确定的、可逐文件解释的：增量恰为 `Libraries/OTA/ota_device_info.c` 与
`ota_device_info.h`，两者由 P3-2 的 `cb2ebdd` 引入，落在立卡锚点 `dd0a995` 之后；
`base(dd0a995)=893`、`worktree=895`、`worktree − base` 恰为该两文件、`base − worktree`
为空。该逐文件核对已固化进 `p3_7_verify_wiring.py`，今后不会再退化为笼统表述。

### 2.2 harness 双向鉴别力

fail-closed 只能保证「没证据必红」，不能保证门禁有鉴别力。两个方向都已实测：

- `inject_probe.py`：对 workflow 做 5 处单点注错（加 `|| true`、只删 push 一侧
  `paths` 条目、删一条执行行、把新增条目改成 `p3_1_verify_*.py` 通配、改
  `jobs.build.name`），每次都 rc=1 且新红落在对应判据（分别新增 5/7/8/13/3 条红项），
  每次按字节存档还原并以 SHA-256 校验、红项集合复原至基线。
- `ci_harness_selftest.py`：用合成的格式良好证据驱动 `p3_7_verify_ci_evidence.py`
  能变绿（197 项核对零失败，证明它不是永久红），再施加 6 类伪造/无效证据全部变红，
  含最关键的 M2「无效注错选点」。自检临时件全部清理，`docs/` 下零落盘。

**本轮亦自查出并修掉了我方核验器的一处空转绿**：互镜判据原先把
`WIRED_SCRIPTS` 常量当 glob 模式用，字面文件名永远匹配不到别的脚本，该断言恒真。
改为用**实际观测到的**新增条目集合，并加空集守卫与阳性对照。修前注入 I4（改通配）
不会被发现，修后产生 13 条新红。

## 3. 发现

### F-1 看板 §10 日志行缺 Markdown 列表标记（产品面，须修，阻断收口）

`PLAN-OTA-EXEC.md` 第 979 行以 `2026-09-03 ｜ Claude(P3-7 实现 agent…` 开头，
缺前缀 `- `；§10 内其余 181 条日志行全部带该前缀。属渲染层格式缺陷，非内容错误。

修复须用 Python 字节编辑：该文件混合 EOL（CRLF/裸 LF 并存），Edit 类工具会整文件
归一，产生上百行伪 diff。实现方在 workflow 上已踩过同一坑并正确规避，看板此处属遗漏。

### F-2 零次真实 CI 运行（证据面，本轮判定缺口的唯一硬原因）

见 §1。已把要求固化为可离线复算的门禁 `tests/ota/p3_7_verify_ci_evidence.py`：
它读取冻结在 `docs/acceptance-contracts/P3-7-v1/ci/` 下的 `gh` 采集件，核对
run 元数据、步骤序号与结论、12 行命令回显、三条接线标记、红点归属、
pipefail 短路、触发器反证提交的改动文件集合，以及**绿运行处的 workflow 字节与
最终落树字节一致**（只凭「某次 run 绿了」不能证明绿的是最终门禁）。

### F-3 三处 CI 注错选点中两处无效（方案面，推送前必须换点）

实现方拟用于 CI 反证的三处选点里，两处会使反证空转。步骤在 `set -euo pipefail`
下线性执行，三条新增行是第 9/10/11 条命令，`python3 tests/ota/test_ota_ble_frame.py`
是第 8 条：

- **改 `OTA_BLE_SYNC0` 0xA5u→0xA55u**：`tests/ota/test_ota_ble_frame.c` 大量使用
  该宏且第 112 行硬编码 `0xA5u`，会先红在第 8 条；
- **往 `Libraries/OTA/ota_ble_ring.h` 插反斜杠 `#include`**：同一 C 用例第 2 行
  `#include "OTA/ota_ble_ring.h"`，Linux 上先编译失败，同样先红在第 8 条。

两种情况下第 9-11 行从未执行，「红」与本卡接线无关。本地反证不受影响（三条脚本
单独跑），但 CI 版必须换点。逐符号实测后的安全替代：

| 反证 | 命令位 | 安全选点 | 依据 |
|---|---:|---|---|
| 合同对齐 | 9 | `Libraries/OTA/ota_ble_frame.h` 的 `OTA_BLE_LEN_ACK_OTHER` 9u→8u | 该常量被 `p3_1_verify_contract_alignment.py` 逐值核对，且 `tests/` 下任何 `.c/.h/.py` 均不引用 |
| 文本隔离 | 10 | 沿用实现方原选点：`USER/HAL/HAL_Bluetooth.cpp` sink 守卫 | 仅被 `p3_1_verify_text_isolation.py` 与 `p3_2_verify_scope.py` 读取，不参与任何 host 测试编译 |
| 可移植性 | 11 | `USER/HAL/HAL_USB.cpp` 插一条反斜杠 `#include` | 在 portability 扫描目录内，且不被 align/iso/`tests/` 下任何文件引用 |

`contract_alignment` 涉及的 18 个 `OTA_BLE_*` 符号里 11 个被前 8 条 host 测试引用，
均为不安全选点；安全的实际只有 `OTA_BLE_LEN_ABORT`/`LEN_ACK_BEGIN`/`LEN_ACK_OTHER`/
`LEN_GET_INFO` 四个。

**推送前置检查（强制）**：每次注错后，先在本地按 CI 同序跑完 11 条命令，确认第
1-8 条仍全绿、红点落在预期那一条，再推送。`p3_7_verify_ci_evidence.py` 已把
「红运行必须含全部 8 条前置标记」写成硬判据，无效选点会被判失败而非通过。

### F-4 P3-6 冻结 harness 现为红（治理面，不阻断，已登记，须留档）

`tests/ota/p3_6_verify_ci_wiring.py` 对当前树返回 rc=1 /
`P3_6_CI_WIRING=FAIL checks=2 failures=2`：步骤名按本卡要求改动后，它按旧名
`Test Boot fw_header validator vectors` 定位不到目标步骤，于 2 项核对后提前中止。
其第 4 项断言 `"p3_1_verify" not in text` 编码了 P3-6 的裁定「8 个脚本一个都不接入」，
本卡为其中三条推翻了该裁定——今天这条断言只因提前中止而未执行，语义冲突真实存在。

不阻断的依据：该脚本未被任何 workflow 执行（`firmware-build.yml` 与
`acceptance-governance.yml` 的执行清单均已逐行核对），不打红任何在跑门禁；裁定反转
已在看板 §9（2026-09-03 P3-7 立卡批次）、§6 P3-7 卡「分类补正」与
`P3-7-card-creation.md` §4 三处登记。P3-6-v1 的可复现性由其锚定提交承载。
留档目的是让后续会话不把 `P3_6_CI_WIRING=FAIL` 误读为新回归。

### F-5 又一条产品 host 测试无人执行（范围外，建议立新卡）

`tests/ota/test_ota_device_info.py`（P3-2 于 `cb2ebdd` 落地）不被任何 workflow 执行
（`grep device_info .github/workflows/*.yml` 零命中）。本会话实跑：rc=0，
`P3_2_OTA_DEVICE_INFO checks=114 failures=0` / `P3_2_OTA_DEVICE_INFO_ALL=PASS`，
外部耦合仅 `shutil.which("cc"/"gcc"/"clang")`，Ubuntu runner 具备。即 P3-7 要消除的
同一类缺口的新实例。

**不并入本卡**：派工书「允许修改范围/非目标」已冻结，扩范围会使本卡验收失去边界。
公允地讲，`tests/ota/` 下另有若干 `test_*.py`（backup、sd、update、p2_6_* 等）同样
未接线，其中部分可能因依赖真机或构建产物而**本应**排除——所以这里只报告
`device_info` 这一个确证实例，不宣称它是唯一异常，也不预判其余各条的归属。
建议新卡的第一件事就是逐条实跑分类，方法照 `P3-7-card-creation.md` §3。

## 4. 对实现方提出的 squash 收口方案的裁定

**准许 squash，但附三项条件。** 本卡与 P3-2 的裁定相反，理由不是先例偏好而是
冻结点是否会被压掉：

- P3-2 禁止 squash，因为证据包与被绑定的看板字节在同一提交序列里，压掉即无任何
  提交持有 manifest 绑定的那份看板字节，包永远无法再校验；
- P3-7 与 P3-6 同型：CI 证据由包内冻结的 `ci/**` 采集件承载，不依赖注错提交在
  `main` 上的可达性；需要保留的只是**最终树**。

条件：
1. 三份 manifest 必须针对**最终树**（含验收回写后的看板）生成，squash 后的单提交
   树与之逐字节一致；
2. 刻意注错的提交不得进入 `main`——这正是 squash 的目的；
3. 绿运行与最终门禁的同一性由 `ci/workflow-at-<head>.yml` 承担（§3 F-2 已实现该判据），
   不得改用「提交可达性」来证明。

## 5. 合同冻结与证据包的推迟（含理由）

本轮**故意不生成**合同/证据矩阵/三份 manifest，理由与既有教训一致：Governance
profile 绑定 `PLAN-OTA-EXEC.md` 字节，而看板必然还要再变两次（F-1 修复 + 验收回写）；
先生成即保证整批重做。按「看板回写早于 manifest 生成」的既定顺序，合同与包在
**CI 证据齐备的那一批次**一次性冻结并过 `Tools/acceptance/validate_bundle.py`。

本轮的判定依据不是临时拟定的标准：用的是已入库的冻结派工书完成判据与看板卡验收
字段；缺口本身也已表述为可复算门禁（`p3_7_verify_ci_evidence.py`），不靠文字描述。
`EVIDENCE_GAP` 按规约不属于必须绑定产物的结果类别（那是 PASS 与产品/harness FAIL 的
要求），故本轮不存在「该绑产物而未绑」的问题。

## 6. 收口条件（按顺序）

1. 修 F-1（看板第 979 行补 `- `，Python 字节编辑）。
2. 用户放行推送后，在特性分支按 §3 修正后的选点取 8 次 CI 运行：正例、触发器反证、
   三次注错红、三次还原绿；每次注错前先跑本地 11 条同序预检。
3. `gh` 采集件冻结进 `docs/acceptance-contracts/P3-7-v1/ci/`，回填
   `p3_7_verify_ci_evidence.py` 的 run 标识常量并跑到绿。
4. 验收回写看板 + §10 追加一行（不记任何哈希）。
5. 冻结 `P3-7-v1` 合同 / 证据矩阵 / 三份 manifest，跑校验器，出第 2 轮结论。
6. F-5 另行立卡。

## 7. 我方派工书的两处缺陷（自认，非实现方责任）

- **结构缺陷（与 P3-2 的 F-2 同类）**：完成判据要求真实 CI 运行日志、run 标识与提交
  SHA，而看板 §0 规则 8 禁止实现方 `commit/push/merge`——判据要求了实现方在结构上
  被禁止产出的证据。派工书本应把 CI 取证明确划为主会话职责并写入交付切分，而不是
  列进实现方的完成判据。
- **措辞缺陷**：「计数与 `P3-7-card-creation.md` §3 的本机基线一致」未区分判据字段与
  信息字段。字面读会把 `portability` 的 `scanned` 895≠893 判为不一致，而它是随目录
  内容变化的信息字段。后续同类判据应逐字段声明「判据字段」或「信息字段」。

两处均不改动已冻结的派工书文本，在此登记，后续卡以本节为准。

## 8. 本轮可复算命令清单

```
python -X utf8 -B tests/ota/p3_7_verify_wiring.py
python -X utf8 -B tests/ota/p3_7_verify_ci_evidence.py
python -X utf8 -B tests/ota/p3_1_verify_contract_alignment.py
python -X utf8 -B tests/ota/p3_1_verify_text_isolation.py
python -X utf8 -B tests/ota/p3_1_verify_portability.py
python -X utf8 -B -m unittest tests.ota.test_acceptance_bundle
python -X utf8 -B tests/ota/p3_6_verify_ci_wiring.py     # 预期红，见 F-4
python -X utf8 -B tests/ota/test_ota_device_info.py      # 预期绿，见 F-5
python -X utf8 -B .cache/p3-7-accept/inject_probe.py
python -X utf8 -B .cache/p3-7-accept/ci_harness_selftest.py
```
