# P2-6-v3 冻结、独立复算与校验器 fail-closed 反证（2026-09-01）

**会话性质**：非实现独立验收会话（承接 P2-6-SD-R7 / R8 / R9 的硬件轮次）。
本会话不写任何生产源码、不改任何冻结契约与门槛数字，只做独立复算、冻结与回填。

**总结论**：P2-6「升级态 RAM 峰值实测回填」整卡 **PASS**。预算表闭环——全部实测
≤ P0-6 设计预算，**不触发 16KiB→8KiB 字典降档**，`40960B` / `8192B` / `16KiB` /
`35492B` / `5468B` 五个冻结数字一个未改。

---

## 1. 冻结件与哈希

| 项 | 值 |
| --- | --- |
| 合同 | `docs/acceptance-contracts/P2-6-v3.contract.json` |
| 合同 SHA-256 | `DA78DDF5BDCA97E1848522193F4FE9F4E7D8E6AC02B0471DFB8F45D9B8AC19B4` |
| 合同标识 | `contract_id=P2-6-v3`、`task_id=P2-6`、`version=3`、`status=FROZEN` |
| 父合同绑定 | `parent_contract_sha256=0332FEE70D7486C41EF53EC184376A069467DD67C8E80E5744B28B33F9471F62`（= P2-6-v2 合同字节） |
| 证据矩阵 | `docs/acceptance-contracts/P2-6-v3/P2-6-v3.evidence-matrix.json` |
| 矩阵 SHA-256 | `017FAF6E07D6B87F98262D946F3C9547AC40AFC5BB0218188CC253E346449683` |
| 轮次 | `P2-6-V3-FREEZE-20260901-01` |
| 规模 | 27 判据 / 8 命令 / 62 产物 |
| 整体结果 | `overall_result=PASS`，27 判据全 `EXECUTED`/`PASS` |
| 复用绑定 | `previous_matrix_sha256`、`rerun_plan_path`、`rerun_plan_sha256` 三项全 `null`（本轮不走复用通道） |

三类输入 manifest（由 `Tools/provenance/source_manifest.ps1` 按
`Tools/provenance/manifest_profiles.json` 的 profile 定义现场枚举生成）：

| 输入组 | profile | FileCount | ManifestSHA256（前 16） |
| --- | --- | --- | --- |
| production | Production | 2912 | `F173B6780A911FE9` |
| validation | Validation | 130 | `5BFCBB28C590F3EC` |
| governance | Governance | 24 | `A611FCE9B3B90649` |

Governance manifest 的 Head 为 `577e103efd0da5dd005c6cbf8e3cee08e7a8c0aa`。

六项外部输入已按合同登记指纹与证据哈希：R8/R9 两个硬件轮次（`hardware_state`）、
GOOD/BAD 两个 `.etu` 夹具（`fixture`，`target_vcode=20802`，BAD 为 `payload_flip@141209`）、
生产/插桩两个冻结 ELF（`toolchain`）。

---

## 2. 为什么不走 `REUSED` 通道

R5/R8/R9 的原始产物已存在，按验收规约本可以标 `REUSED` 并绑定上一轮矩阵。本轮
**主动放弃复用通道**，全部 27 判据标 `EXECUTED`，理由是复用只能证明"上一轮说过"，
不能证明"这一轮从原始字节还能算出同样的数"。

代之以本会话自写的 fail-closed 复算 harness：

```text
tests/ota/p2_6_v3_evidence_recompute.py --bundle docs/acceptance-contracts/P2-6-v3
P2_6_V3_RECOMPUTE criteria=23 failed=0 status=PASS
REPORT=docs\acceptance-contracts\P2-6-v3\artifacts\recompute\p2-6-v3-recompute-report.json
EXIT=0
```

它不读任何轮次的结论字段，只从 R5/R8/R9 落盘的**原始 RTT 日志、result.json、
dump 出的二进制、map/ELF** 现场重算 23 条判据（其余 4 条由 `tests/ota/` 下的
三个离线脚本与栈闭合单测直接执行）。harness 自身也带自检：

```text
tests/ota/p2_6_v3_evidence_recompute.py --selftest
P2_6_V3_SELFTEST positive=1 negative=32 failed=0 status=PASS
EXIT=0
```

32 条负例覆盖"观测值被改一位""决定性产物被删""托管文档被篡改""生产/插桩 OTA
布局不一致""容量下界用例被改成成功"等形态，确认 harness 不是常量 PASS。

---

## 3. 八条命令与退出码

| 命令 ID | 内容 | 退出码 |
| --- | --- | --- |
| `CMD-V3-STACK-CLOSURE` | `tests/ota/test_p2_6_stack_closure.py`（7 用例，显式传入 `P2_6_PROD_STACK_BUILD` / `P2_6_TEST_STACK_BUILD`） | 0 |
| `CMD-V3-SYMBOLS` | OTA 段与符号地址导出 | 0 |
| `CMD-V3-CAPACITY` | `tests/ota/test_p2_6_capacity.py` → `P2_6_CAPACITY=PASS` | 0 |
| `CMD-V3-CONFIGURATION` | `tests/ota/test_p2_6_configuration.py` → `P2_6_CONFIGURATION=PASS` | 0 |
| `CMD-V3-LINK-ASSERTS` | `tests/ota/test_p2_6_link_asserts.py` → `P2_6_LINK_ASSERTS=PASS positive+A1+A2+A4+A5+A6` | 0 |
| `CMD-V3-RAM-HIGHWATER` | 生产/插桩两构型 RAM 布局导出 | 0 |
| `CMD-V3-RECOMPUTE` | 独立复算 23 判据 | 0 |
| `CMD-V3-RECOMPUTE-SELFTEST` | 复算 harness 自检（1 正例 + 32 反例） | 0 |

全部 stdout 落盘于 `docs/acceptance-contracts/P2-6-v3/commands/`，并按路径/大小/
SHA-256 登记进矩阵。

---

## 4. 关键实测值（全部由本会话独立复算得出）

**真机 FULL 升级路径**（R8，2026-08-31；固件自身 Apply→Stage→复位→boot 消费，
App slot `vcode 20800→20801`）：

- overlay workspace 峰值 `33016B` ≤ `40960B`，占 `80.61%`，余 `7944B`
- `arena_peak == workspace_peak`，`failed_request_size=0`，全程恰一条 FULL 测量记录
- OTA 调用栈峰值 `3496B` ≤ `8192B`，占 `42.7%`，余 `4696B`；`32B` guard 进入与退出均完整
- `sbrk` 增量 `0`；`lv_tlsf_{malloc,realloc,free}` 增量均 `0`
- `lv_mem_monitor` 四字段进出净零（free 63616 / big 59900 / frag 6 / max 64667）

**真机 PATCH 升级路径**（R5，2026-08-30，已由 P2-6-v2 冻结）：workspace 峰值
`21792B` ≤ `40960B`（占 `53.2%`，余 `19168B`）；guard 完整；`sbrk` 与 TLSF 三项增量同为 `0`。

**静态栈闭合**（§4.9-E 路线，`OFF-C3-C13-STACK-CLOSURE`）：线程峰值取两条路径的较大者
`2048B`（FULL `1904B` / PATCH `2048B`），加最坏中断预算 `768B`，总上界 `2816B` ≤ `8192B`，
余 `5376B`；`interrupt_evidence_gaps=[]`；扫描点自身开销 `16B`、测量包装函数上界 `40B`
分别独立报告。

**RAM 布局**（`OFF-C8-C16-RAM-LAYOUT`）：主 RAM 区 `360448B`，区顶 `0x20058000`；生产已
分配 `357088B`（堆空洞 `3360B`）、插桩 `357264B`（堆空洞 `3184B`），差值即插桩增量 `176B`；
生产与插桩两构型的三个 OTA 段逐字段一致——`.ota_stack_guard` `0x20055FE0`/`32B`、
`.ota_stack` `0x20056000`/`8192B`、`.ota_overlay` `0x20058000`/`40960B`；`.sram_ext`
保持 `163840B`；`production_fits_region=true`。

**宿主容量判别**（`OFF-C10-C11-CAPACITY`）：FULL `prefix=6576`、`P_full=33072`，
`26496` → `ok` / `26495` → `workspace`（`failed_request_size=16384`）；PATCH `prefix=7640`、
`P_full=21848`，`14208` → `ok` / `14207` → `workspace`（`failed_request_size=4096`）；
两侧均在 ±1B 处翻转。

**交叉核对**：真机 FULL 峰值 `33016B` 比宿主模型 `P_full=33072B` 低 `56B`，方向与量级
与宿主模型一致、未反超门槛。该 `56B` 差值本轮**未逐项定界**，因此不作为任何门槛或
分项预算的依据，仅作为一致性佐证记录。

**保管完整性**（`PROC-CUSTODY-COMPLETE`）：52 项冻结产物、2979503 字节；申报缺口 ==
观测缺口 == `artifacts/r9/p2-6-sd-r9-bad-upload-hw-01-result.json`（见 §6 F1）。

**C9**（AC5 辅助工具链）按冻结提示词保持 `NOT_OBSERVED` 且不阻塞；C1-C8、C10-C16
全部取得实际观测并通过。

---

## 5. 校验器 fail-closed 反证（18 例，escaped=0）

`validate_bundle.py` 退出码 0 本身没有证明力——除非先证明它在**本证据包上**确实会因
单点篡改而失败。为此对已冻结的合同/矩阵逐个注入单点变异，每次跑一遍校验器、要求非零
退出，再用生成器重建原文件：

```text
[baseline] exit=0 PASS
[negative] 矩阵观测值偏离冻结门槛: exit=1 CAUGHT
[negative] 合同门槛事后放宽: exit=1 CAUGHT
[negative] 产物哈希与磁盘不符: exit=1 CAUGHT
[negative] 产物大小与磁盘不符: exit=1 CAUGHT
[negative] 证据哈希表被篡改: exit=1 CAUGHT
[negative] 命令退出码越界: exit=1 CAUGHT
[negative] 命令串誊抄漂移: exit=1 CAUGHT
[negative] 矩阵绑定的合同哈希错误: exit=1 CAUGHT
[negative] manifest 内部哈希错误: exit=1 CAUGHT
[negative] manifest 文件哈希错误: exit=1 CAUGHT
[negative] 缺少 Governance 输入组: exit=1 CAUGHT
[negative] PASS 判据产物未登记: exit=1 CAUGHT
[negative] PASS 判据命令未登记: exit=1 CAUGHT
[negative] 外部输入证据哈希错误: exit=1 CAUGHT
[negative] 未绑定上一版合同: exit=1 CAUGHT
[negative] 结果分类被扩容: exit=1 CAUGHT
[negative] 有 FAIL 判据仍宣告整体 PASS: exit=1 CAUGHT
[negative] 声称 REUSED 却无上一轮绑定: exit=1 CAUGHT
[restore] exit=0
P2_6_V3_VALIDATOR_SELFTEST negatives=18 escaped=0 status=PASS
```

18 例全部被拦截、无一逃逸；baseline 与 restore 均 `EXIT=0`，证明变异脚本能精确还原
冻结字节（还原后合同 SHA-256 仍为 `DA78DDF5…19B4`，与冻结值逐字节一致）。

反证脚本：`.cache/p2-6-v3-build/validator_selftest.py`；日志：
`.cache/p2-6-v3-build/validator-selftest-20260901.log`。它刻意**不**列入合同的 8 条命令，
因为它会临时改写合同本身，不能同时充当被校验对象与证据。

最终校验：

```text
python Tools/acceptance/validate_bundle.py \
  --contract docs/acceptance-contracts/P2-6-v3.contract.json \
  --matrix docs/acceptance-contracts/P2-6-v3/P2-6-v3.evidence-matrix.json \
  --repo-root D:/github/my/E-Track
VALIDATION=PASS contract=P2-6-v3 round=P2-6-V3-FREEZE-20260901-01 overall=PASS
EXIT=0
```

---

## 6. 写入顺序与自指规避

`PLAN-OTA-EXEC.md` 属 Governance profile 的 `top_files`，任何编辑都会改变
Governance `ManifestSHA256` → 改变合同内容 → 改变合同 SHA-256。因此在看板里登记
"本合同 SHA-256"是自指的，做不到。本轮采用的顺序是：

1. 先完成看板回写（P2-6 卡状态、整卡验收条目、§10 会话日志）；
2. 再重新生成 Governance manifest；
3. 再重新生成合同与矩阵（合同 SHA 由 `D2A435CF…5991` 变为 `DA78DDF5…19B4`）；
4. 再跑校验器与 18 例反证；
5. 最后才写**不属于任何 profile** 的三处文档并在其中登记最终合同 SHA。

`PLAN-OTA.md`、`docs/ota-binary-contracts.md`、`docs/ota-exec-notes/`（含本文件）
均不在任何 profile 的枚举范围内，因此这三处回填不会使已冻结的 manifest 失效——该
性质已在 `Tools/provenance/manifest_profiles.json` 中逐条核对。看板中因此**不记**
合同哈希，只指向 `PLAN-OTA.md` §9 与本文件。

回填去向：

- `PLAN-OTA.md` §9：新增「升级态峰值实测回填(P2-6 真机闭环,2026-09-01)」一条，
  纯追加，明确声明取代上一条尾部的 `NOT_OBSERVED` / `EVIDENCE_GAP` 结论。
- `docs/ota-binary-contracts.md` §10.1 与 §10.3：各追加一段实测回填，声明
  "不修改本节任何门槛"，并点名作废 §10.3 中"J-Link DAP 初始化失败导致真机
  C1-C7/C14 未观测"的旧句。
- `PLAN-OTA-EXEC.md`：P2-6 卡状态由「进行中」改为「完成」，原「未观测」「阻塞」
  两项原文保留、标注为历史并说明分别由 v2 / v3 闭合。

---

## 7. 如实登记的遗留项与瑕疵（均不阻塞 P2-6，转后续处理）

**遗留项**

- **F1**：R9 上游 manifest 未覆盖 `artifacts/r9/p2-6-sd-r9-bad-upload-hw-01-result.json`。
  已在矩阵中以"申报缺口 == 观测缺口"如实登记，`PROC-CUSTODY-COMPLETE` 因两者相等而
  PASS，不是把缺口当成不存在。
- **F4**：v2.8.2 GOOD/BAD 资产尚未写入仓库冻结常量，目前只作为 `external_inputs`
  以指纹+证据哈希绑定。
- **F6**：SD 卡上 R9 留下的 BAD 包残留待清理（本会话无硬件操作授权，未动）。

**两条 harness 缺陷（属实现侧范围，本验收会话不自修，以免自证）**

- `tests/ota/test_p2_6_capacity.py`、`test_p2_6_configuration.py`、
  `test_p2_6_link_asserts.py` 是 `__main__` 脚本，pytest 收集 0 用例却报绿。
  本合同以脚本方式直接调用并校验退出码与结论行，故 v3 结论不受影响。
- `tests/ota/test_p2_6_stack_closure.py` 的默认构建候选指向陈旧树，正确根为
  `.cache/p2-6a-cmake-{prod,test}-stack`；本合同经 `P2_6_PROD_STACK_BUILD` /
  `P2_6_TEST_STACK_BUILD` 显式传入，未依赖默认值。

**R7 结论更正的传递**

R7 文档 §2 中"BCB_B magic=`f5ad8999` 非法、CRC 复算不符"一句已被 R8 推翻：R8 以
真实双读（`read_a_rc=1 read_b_rc=1`、`valid_a=1 valid_b=1`、`arbiter=1`）证明 B 块
实为 `ETBC` / `state=5(ROLLBACK)` / `seq=751`、块内 CRC32 复算一致，R7 那句系未真正
读到 B 块造成的残留误读。更正原文见
`docs/ota-exec-notes/P2-6-SD-R8-hw-execution-evidence-2026-08-31.md`。R7 的 D1 四字段
对照使用的是 A 块数据，**仍然有效**。R7 文档已作为冻结产物入包，本会话不改其字节，
更正只在此处与 R8 文档中登记。

**冻结提示词的交叉引用瑕疵**：判据表把 C7 标注为「§4.5 第 3 项」，实际对应 §8 第 5 项。
仅为引用编号错误，判据语义未受影响，本轮按语义执行。

---

## 8. 复现命令

```text
# 1) 重新生成合同与矩阵（读取三份 manifest 的 ManifestSHA256）
python -B .cache/p2-6-v3-build/emit_contract_matrix.py

# 2) 校验证据包
python -B Tools/acceptance/validate_bundle.py \
  --contract docs/acceptance-contracts/P2-6-v3.contract.json \
  --matrix docs/acceptance-contracts/P2-6-v3/P2-6-v3.evidence-matrix.json \
  --repo-root D:/github/my/E-Track

# 3) 独立复算与自检
python -B tests/ota/p2_6_v3_evidence_recompute.py --bundle docs/acceptance-contracts/P2-6-v3
python -B tests/ota/p2_6_v3_evidence_recompute.py --selftest

# 4) 校验器 fail-closed 反证（会临时改写合同/矩阵并自动还原）
python -B .cache/p2-6-v3-build/validator_selftest.py
```
