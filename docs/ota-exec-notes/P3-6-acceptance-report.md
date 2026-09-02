# P3-6「BLE 帧层测试 CI 接线」独立验收报告

- 验收角色：独立验收会话（非实现方），实现方为 `Claude(实现会话)`
- 验收日期：2026-09-02
- 轮次：`P3-6-V1-FREEZE-20260902-01`
- 单轮结果：**PASS**（合同制正式验收，13 条判据全部 `EXECUTED PASS`，无 `REUSED`）
- 综合评分：**94 / 100**
- 被验收 Head：`a9cf6f7fb0802059b52b67225851260e81728f90`，基线 `main` = `ded14e8cb476`
- 收口状态：**尚未收口**。按 `AGENTS.md` §「OTA 执行规约」第 5 条，验收会话不执行
  `git commit/push/merge`，收口由主会话在用户确认后进行。

本报告是本轮验收的哈希与数值落盘处。看板 `PLAN-OTA-EXEC.md` 是 Governance profile 的
`top_file`，其中**不得记录任何哈希（含 commit SHA）**，否则看板一改就使 Governance 指纹漂移，
形成不收敛的自指环；因此看板只回写状态与结论，指纹全部留在本文件。

---

## 1. 冻结合同与证据包

| 项 | 路径 | 字节 | SHA-256 |
| --- | --- | --- | --- |
| 验收合同 | `docs/acceptance-contracts/P3-6-v1.contract.json` | 27314 | `E80966AAA3EC17C4A00F3B8A7378DA31AB13F629135A3E8685F794F9D2276A4C` |
| 证据矩阵 | `docs/acceptance-contracts/P3-6-v1/P3-6-v1.evidence-matrix.json` | 14707 | `BBC78069DFF22B820B6EF2E998CF063DF1FE85FA57479EEC87C41A8862D4B7CB` |

合同标识：`schema=etrack-acceptance-contract-v2`，`contract_id=P3-6-v1`，`task_id=P3-6`，
`version=1`，`parent_contract_sha256=null`（首版），`status=FROZEN`。
矩阵的 `contract_sha256` 绑定的是**合同文件字节**的 SHA-256，与上表一致。
矩阵 `previous_matrix_sha256` / `rerun_plan_path` / `rerun_plan_sha256` 全为 `null`
—— 本轮无证据复用，不存在跨轮复用绑定。

证据包根目录 `docs/acceptance-contracts/P3-6-v1/`，包含 7 份命令原始 stdout、
9 份 CI 采集件、2 份被冻结的外部输入副本、2 份保管产物、3 组 manifest（共 9 个文件）。

### 1.1 为什么证据包落在这个路径

`Tools/provenance/manifest_profiles.json` 的三个 profile 枚举范围：

- Production：`.github/scripts/`、`ArduinoAPI/`、`Libraries/`、`USER/`、`boot/`、
  `bsdiff_lzma_AES128-main/`、`cmake/`、`MDK-ARM_F435/Platform/`、
  `MDK-ARM_F435/RTE/Device/-AT32F435RGT7/`、`MDK-ARM_F435/RTE/_X-Track/`、
  `MDK-ARM_F435/cmake-generated/cmake/`、`Simulator/LVGL.Simulator/`、`segger_rtt/`、
  `vendor/` + 7 个 `top_files`
- Validation：`Tools/`、`tests/` + 3 个 `top_files`（仅 `docs/acceptance-contracts/template.*`）
- Governance：`docs/ota-prompts/` + 6 个 `top_files`（含 `PLAN-OTA-EXEC.md`）

`docs/acceptance-contracts/P3-6-v1**`、`docs/ota-exec-notes/**`、`.claude/**` 均不被任何
profile 枚举，因此写入合同、矩阵、本报告与审查报告都**不会使已生成的三份 manifest 失效**。
这一点是收敛顺序的前提：本轮实际执行顺序为
**看板回写 → 生成三份 manifest → 实跑 7 条命令 → 冻结合同 → 生成矩阵 → 校验器**。
若把看板回写放到 manifest 之后，Governance 指纹必然过期而校验失败。

### 1.2 落盘后复跑确认（DEV-4 的实测验证）

合同与矩阵入包后再次复跑（不覆盖包内日志，仅确认门槛仍成立）：

- `p3_6_verify_scope.py`：`untracked` 由 39 变为 41，但 `=== 失败项 0 / 核对项 70 ===`、
  `P3_6_SCOPE=PASS checks=70 failures=0` 不变，exit=0。
- `tests/ota/test_acceptance_bundle.py`：`Ran 65 tests in 34.881s` / `OK`，exit=0。

这正是 DEV-4 的设计目的：`SCOPE-*` 判据的门槛只绑定语义不变量
（`result=PASS` / `red_line_diffs=0` / `committed_changed=7` / `failures=0`），
未绑定核对项总数。若当初把 `checks=70` 之外的逐文件计数写进门槛，矩阵在自身落盘的
那一刻就会失效。

---

## 2. 三类 manifest 指纹

| profile | 文件数 | `manifest_sha256`（内部稳定指纹） | `manifest_json_sha256`（JSON 文件字节） |
| --- | --- | --- | --- |
| Production | 2918 | `D7A9EDA136442B873EF1C0DE25CE8C21C85D07E83F25615B4163DDFDBBEA8FD9` | `1068322ED08311AA474D7AF3BCB6B8F5A5555F589D9ED1E3A2BA965DCDCF55BC` |
| Validation | 146 | `F5EA1A38FC8FD91BE308401E925F3425C2A5D847C7ED38651A6F493604E82858` | `D5F4320FFEB5F2E660E87983F7D83304759F6A2898B0D8013B627EC365B5BD8F` |
| Governance | 25 | `123C9F7D7172B73CEF4B0EE4BC6AD7D4E2E77B86282648892BBE4214A8483D4E` | `08A217984494EDB39279CBF9915DF6BEE7C99CDCCB64A862358B407025ED6793` |

三组均 `Result: PASS`、`Head: a9cf6f7fb0802059b52b67225851260e81728f90`。
`manifest_sha256` 是文件集内部稳定指纹（`{SHA256}  {Length}  {Path}` 行以 CRLF 连接后取
SHA-256，大写），等于 `source-manifest.txt` 的字节哈希；`manifest_json_sha256` 是 JSON 文件
自身的字节哈希。两者不可混用：前者用于产品复验失效判定，后者只校验证据完整性。

---

## 3. 13 条判据与实测观测值

全部 `execution=EXECUTED`、`result=PASS`、`reused_from_round=null`、`failure_owner=null`。
`observed` 由 `.cache/p36-accept/write_matrix.py` 从包内 `commands/*.log` **逐元素正则派生**
后与冻结 `gate.expected` 断言全等，不是从门槛反抄——派生不出或不相符即抛错。

| # | 判据 | kind | observed（= 门槛，实测派生） |
| --- | --- | --- | --- |
| C01 | `WIRING-COMMAND-SEQUENCE` | process | `result=PASS` / `step_commands=9` / `wired=2` |
| C02 | `WIRING-PURE-ADDITION` | process | `result=PASS` / `added=2` / `removed=0` / `trigger_lines=57` |
| C03 | `WIRING-FAIL-CLOSED-SEMANTICS` | safety | `result=PASS` / `checks=32` / `failures=0` |
| C04 | `WIRING-CLASSIFICATION-RULING` | process | `result=PASS` / `failures=0` |
| C05 | `CI-BASELINE-GREEN-MARKERS` | functional | `run=33620407886` / `run_conclusion=success` / `step10=success` / `frame_marker=1` / `session_marker=1` |
| C06 | `CI-DEFECT-RUN-RED-ATTRIBUTED` | safety | `run=33621049995` / `run_conclusion=failure` / `red_at_step=10` / `session_output=0` |
| C07 | `CI-DISCRIMINATION-CONTRAST` | process | `governance_run=33621050015` / `head=7b58ed6` / `conclusion=success` |
| C08 | `CI-RESTORE-GREEN` | functional | `run=33621403637` / `run_conclusion=success` / `step10=success` / `reds=1` / `defect_then_restore=1` |
| C09 | `SCOPE-PRODUCT-SOURCE-INTACT` | safety | `result=PASS` / `red_line_diffs=0` / `reverted_source_size=11729` / `required_on_main_tracked=4` |
| C10 | `SCOPE-AUTHORIZED-CHANGES-ONLY` | safety | `result=PASS` / `committed_changed=7` / `failures=0` |
| C11 | `LOCAL-RECOMPUTE-PARITY` | functional | `frame_checks=39` / `frame_failures=0` / `session_checks=105` / `session_failures=0` |
| C12 | `HARNESS-FAIL-CLOSED` | process | `result=PASS` / `checks=66` / `failures=0` |
| C13 | `GOVERNANCE-GATE-GREEN` | process | `tests=65` / `result=OK` |

`performance_gates` 为空：本卡无性能判据，因此不存在「把历史测量值加余量反向冻结为门槛」
的风险面。所有 13 条 gate 的 `basis` 均为 `frozen_requirement`。

### 3.1 接线本身（C01–C04）

被接线步骤是 `.github/workflows/firmware-build.yml` 的
`Test Boot fw_header validator vectors`。其 `run` 块命令序列与冻结期望逐行全等：

```text
set -euo pipefail
python3 tests/ota/test_fw_header_vectors.py
python3 tests/ota/test_boot_protocols.py
python3 tests/ota/test_boot_state_machine.py
python3 tests/ota/test_ota_staging.py
python3 tests/ota/test_ota_package.py
python3 tests/ota/test_ota_patch.py
python3 tests/ota/test_ota_ble_frame.py      <= 本卡新增
python3 tests/ota/test_ota_ble_session.py    <= 本卡新增
```

即 `step_commands=9` = 1 条 shell 守卫 + 6 条既有基线 + 2 条新接入（`wired=2`）。
`git diff --numstat` 相对 base 为 `2	0	.github/workflows/firmware-build.yml`
（`added=2` / `removed=0`），触发段 57 行与 base 字节一致，`paths` 仍含
`tests/ota/test_ota_*.py`、`Libraries/**`、`.github/workflows/firmware-build.yml`。

fail-closed 语义：workflow 全文对 `|| true`、`continue-on-error`、`if: always()`、
`set +e`、`|| :`、`exit 0` 六类吞码模式零命中；`set -euo pipefail` 使两条新命令的非零
退出码必然上抛为步骤失败。workflow 全文亦不含 `p3_1_verify` 之类验收专用脚本——
接线的是产品测试，不是验收 harness。

### 3.2 CI 反证链（C05–C08）

| 运行 | Head | 结论 | 第 10 步 | 关键观测 |
| --- | --- | --- | --- | --- |
| 33620407886 | `0a97b988e2aa`（接线提交） | success | success | 帧层/会话层 PASS 标记各 1 次；日志 682 行 |
| 33621049995 | `7b58ed6fd8ee`（注入 CRC 缺陷） | **failure** | **failure** | 红色归因到第 10 步；帧层 39 项 **13 失败**；会话层因 pipefail 短路 `session_output=0`；日志 583 行 |
| 33621403637 | `e3f9b1ab7589`（缺陷已还原） | success | success | 恢复与基线一致的 682 行日志与两个 PASS 标记 |
| 33621050015 | `7b58ed6fd8ee`（同一注错提交） | **success** | — | Acceptance Governance 流水线在同提交上仍绿 |

第 4 行是本轮最关键的一条：它排除了「该提交让所有流水线一起红」的伪鉴别力，
证明红色由**被接线的测试步骤特异性产生**，而不是缺陷把整个 runner 弄坏。
`session_output=0` 同样重要：它证明失败沿步骤边界立即上抛，没有被后续命令掩盖。

分支侧账：12 次运行中仅 1 次红且正是注错提交；PR #14 的 5 条提交中存在
「注错 → 立即还原」相邻对，缺陷未留在分支末端。

### 3.3 范围红线（C09–C10）

20 条产品红线 pathspec（`Libraries/OTA/**`、`boot/**`、`USER/**` 等）相对 `main` 零 diff。
被临时注错的 `Libraries/OTA/ota_ble_frame.c` 已完整还原：11729 字节、
SHA-256 前缀 `07b20f99c37910cc`（完整值
`07b20f99c37910ccec0cdc8223cea58e7823451a9198f952c30ec98e1003e02a`），与 `main` 一致。
四个被接线/依赖的 BLE 测试文件均已在 `main` 入库（`required_on_main=4 tracked=4`）。

相对 `main` 的 7 个已提交改动文件全部落在授权分层内：

| 文件 | 授权分层 |
| --- | --- |
| `.gitattributes` | governance-batch1, acceptance |
| `.github/workflows/firmware-build.yml` | card |
| `PLAN-OTA-EXEC.md` | card |
| `docs/ota-exec-notes/P3-6-ci-wiring-evidence.md` | card |
| `docs/ota-exec-notes/P3-6-governance-change.md` | card |
| `docs/ota-prompts/prompt-P3-6-implementation.md` | governance-batch1 |
| `tests/ota/test_acceptance_bundle.py` | governance-batch1 |

零未授权改动。工作树脏文件（`.gitattributes`、`PLAN-OTA-EXEC.md`）与未跟踪文件同样
只命中授权分层。

### 3.4 本地复算与 harness 鉴别力（C11–C12）

C11：本地用同一脚本复算两套被接线测试，得帧层 `checks=39 failures=0`、
会话层 `checks=105 failures=0`，与 CI 绿运行日志中的标记逐字一致。这同时证明两件事：
CI 里的数字不是环境特有产物；接线没有偷换成弱化版测试。

C12：本卡四个验收脚本自身接受了变异测试——3 组对照沙箱必须通过（排除「恒失败」伪鉴别力），
15 处单点变异必须逐一被捉住，每例核对四件事：退出码非零、打出 `=FAIL ` 标记、
失败原因已在 `EXPECTED_REASONS` 登记、该原因出现在 `FAIL: ` 行上。
共 3 + 15×4 = 66 项，0 失败。

---

## 4. 命令与退出码

7 条命令全部 exit=0，`expected_exit_codes=[0]`，均带原始 stdout 入包。
本机 `python3` 是 Windows 应用执行别名（直接调用返回 rc=49），故本地统一用
`python -X utf8 -B`（附 `PYTHONIOENCODING=utf-8` 使中文 stdout 可读）；CI 侧为
ubuntu-latest 真 `python3`，两侧脚本字节相同（见 DEV-5）。

| 命令 ID | 命令 | exit | 日志 | 字节 | SHA-256 |
| --- | --- | --- | --- | --- | --- |
| `CMD-VERIFY-CI-WIRING` | `python -X utf8 -B tests/ota/p3_6_verify_ci_wiring.py` | 0 | `commands/verify-ci-wiring.log` | 282 | `58C8A0A460F20C4C9C071C64821927AABE8952283D28E184C92D1E07621B8A93` |
| `CMD-VERIFY-CI-EVIDENCE` | `python -X utf8 -B tests/ota/p3_6_verify_ci_evidence.py` | 0 | `commands/verify-ci-evidence.log` | 645 | `BDC46C4269EE5F2A3A3CA43F91B332D32A5EEEC832075C58E1F1BC45A126954F` |
| `CMD-VERIFY-SCOPE` | `python -X utf8 -B tests/ota/p3_6_verify_scope.py` | 0 | `commands/verify-scope.log` | 821 | `7A88DF9174FC41BBC83A01C0715C5BE5032F6F9432C4A97FE791F75E5B757D4D` |
| `CMD-VERIFY-HARNESS` | `python -X utf8 -B tests/ota/p3_6_verify_harness.py` | 0 | `commands/verify-harness.log` | 1357 | `E564EE97338C35A28176F3318904D3C4C8AB024F31D4C2114F73EA9120CD94CE` |
| `CMD-TEST-BLE-FRAME` | `python -X utf8 -B tests/ota/test_ota_ble_frame.py` | 0 | `commands/test-ble-frame.log` | 3084 | `9443B53C1BC1470C031D1E483658FCB74DB96BEA73C270B901D1A9C397FAD276` |
| `CMD-TEST-BLE-SESSION` | `python -X utf8 -B tests/ota/test_ota_ble_session.py` | 0 | `commands/test-ble-session.log` | 8097 | `79F11439DEEC6EA2D97216CB0F48C0EE417EB4FF644ACADD00116092331BA537` |
| `CMD-GOVERNANCE-GATE` | `python -X utf8 -B tests/ota/test_acceptance_bundle.py` | 0 | `commands/governance-gate.log` | 165 | `A5EDC2A540FAC97AA9211139B57FBCD950FEF12535B1824B61CAC3003327ECA1` |

7 条命令实跑后 `git status --porcelain` 未发生变化（`status_unchanged=True`）——
验收命令自身不污染工作树。

---

## 5. 保管产物与外部输入

### 5.1 CI 采集件（`ci/`，9 份）

| 包内路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `ci/run-33620407886.json` | 3603 | `DCFE860AB65B5CDCCF3C926DA538F4043DEB75899B42DB9ADFF9F88C6AAABF99` |
| `ci/run-33621049995.json` | 3603 | `414CBFA5176FA47A205E4636F241292E6F1DB93521166E8E157A0BA28A3E5B45` |
| `ci/run-33621403637.json` | 3603 | `982B9F7714144C8404176D518C68679F19923002439C75FBFFF372DAC9F54FD7` |
| `ci/run-33621050015.json` | 1818 | `F2A4C2301CED15FDBC936963FB39D4DE9D35B2F7CDBE1AD3D8559D3FB33C1291` |
| `ci/runs-branch.json` | 3510 | `05A576224FAA3DEAA78DD98D50A9F56E93E7AFEFC071FF78340E1418109D264E` |
| `ci/pr-14.json` | 8738 | `44B1959395AB674E47C2A10564F5BD57E5983433A96527E85A485AE208FEBD11` |
| `ci/step-33620407886.txt` | 115860 | `F72545A535B250043C00F04E40F31ABC291531C2258EF52A91DD30158DF273D8` |
| `ci/step-33621049995.txt` | 98258 | `F9EC846A08D38B285D4CABA5DF446A8FF530E64A9FF505F1B37AA2EC42163969` |
| `ci/step-33621403637.txt` | 115860 | `821C3F2AA858178020A0C71376F2C90DCBF1A00018DDDC8F71D3B06AB84AFB40` |

### 5.2 保管产物与外部输入副本

| 包内路径 | 字节 | SHA-256 |
| --- | --- | --- |
| `artifacts/firmware-build.yml` | 21482 | `166053E2804DF785D1733E9855F00BE074BC5C5188BAFE662C8CFDD39EB1F0A3` |
| `artifacts/artifact-index.json` | 2957 | `069AE1F46ECC205135F9B2167F801DA6F1FC1ECA5CF281CCC07D27510FC45292` |
| `external/P3-6-ci-wiring-evidence.md` | 14733 | `55F96CBFE77D268843C9429557AC61C40848027B7B41DD657D785120D9B2251C` |
| `external/P3-6-governance-change.md` | 11272 | `48EA6E9FCE8A86CFA28032F52AFE8275A498EE9AE4B0902AC3D28342FC11D33E` |

`artifacts/artifact-index.json` 记录包内 12 份复制字节的出处（3 份来自仓库文件、
9 份来自 `gh` 采集命令），索引本身不含自身哈希以避免自指。

---

## 6. 授权偏离（5 条，已写入冻结合同）

- **DEV-1**：实现方证据笔记与治理变更笔记（`docs/ota-exec-notes/**`）不在任何 profile
  枚举范围内，无法由 `input_groups` 绑定 → 以 `external_inputs`
  `EXT-IMPL-EVIDENCE-NOTE` / `EXT-GOVERNANCE-NOTE` 显式冻结包内副本与 SHA-256。
  profile 范围变更须走 `acceptance-governance` CI，不在本卡处置（沿用 P3-1-v2 DEV-3 先例）。
- **DEV-2**：`gh run view --log` 把 ANSI 颜色码渲染为字面 caret notation（`0x5E 0x5B`，即
  `^[`），而非真实 ESC 字节。包内 `ci/step-*.txt` 按采集所得原样冻结，
  `p3_6_verify_ci_evidence.py` 按同一表示解析标记行。不得为「好看」二次清洗这些字节，
  否则冻结日志与采集命令输出不再一致。
- **DEV-3**：本卡向 `.github/workflows/firmware-build.yml` 追加 2 行，该文件是 Production
  profile 的 `top_file`，因此已冻结的 **P3-1-v2 Production 指纹相对当前 HEAD 必然漂移**
  （P3-1-v2 记录 `9A63A80F44935978B2294EF8BB58F6C9CF434E720025C3D8032403B0CCC3E598`，
  本轮重新枚举得 `D7A9EDA136442B873EF1C0DE25CE8C21C85D07E83F25615B4163DDFDBBEA8FD9`；
  两者 `file_count` 同为 2918，差异仅来自该 2 行）。**如实声明、不修复**：冻结资产禁止回改，
  P3-1-v2 的 PASS 绑定其自身 Head，本合同用本轮重新枚举的 Production manifest
  作为唯一生产侧指纹。
- **DEV-4**：`p3_6_verify_scope.py` 的核对项总数依赖工作树跟踪状态，不是不变量 →
  `SCOPE-*` 判据只绑定语义不变量，禁止把核对项总数写进门槛。该脚本已把未跟踪文件收敛为
  单个聚合核对项。§1.2 的复跑实测证明了该处置的必要性。
- **DEV-5**：本机 `python3` 是 Windows 应用执行别名（rc=49），本地统一用
  `python -X utf8 -B`；CI 侧为真 `python3`，两侧脚本字节相同，
  `LOCAL-RECOMPUTE-PARITY`（C11）即用于核对两侧 `checks/failures` 一致。

---

## 7. 冻结口径排除项（`scope.excluded_by_freeze`）

1. **远端 CI 重跑与固件构建本地复算**：本卡冻结任务源（看板 P3-6 卡验收字段与派工书完成
   判据）要求的是「两套 BLE host 测试接入 `firmware-build.yml` 且 fail-closed 可反证」，
   不要求验收方重跑流水线。按规约不得事后追加为验收门槛。
2. **步骤名与内容漂移**：见 §8 发现 1。
3. **注错临时提交仍在分支历史**：见 §8 发现 2。

`scope.not_observed` 为空——13 条判据全部实跑，无「不观测但不阻断」项。

---

## 8. 不阻断发现（不影响本轮 PASS，建议后续处置）

### 发现 1：步骤名与实际内容漂移

被接线步骤仍名为 `Test Boot fw_header validator vectors`，但其 `run` 块实际执行
6 项基线 + 2 项 BLE 共 8 条测试命令，早已超出「Boot fw_header 向量」范畴
（基线 6 条中已含 `test_ota_staging` / `test_ota_package` / `test_ota_patch`）。

- 定性：**本卡接线前既已存在**，不属本卡引入，本卡只是把偏差从 6 条放大到 8 条。
- 影响：CI 失败时步骤名会误导排障方向；不影响 fail-closed 语义与测试有效性。
- 建议：后续卡把该步骤改名为 `Test OTA/Boot host test suites`，或拆成
  `Boot` 与 `OTA` 两个步骤。改名会改动 Production `top_file`，须走独立卡与新一轮验收，
  不宜夹带在本卡收口里。

### 发现 2：注错临时提交 `7b58ed6` 仍在特性分支历史

为取得 fail-closed 反证，实现方刻意提交了含 CRC 缺陷的 `7b58ed6`，
并在下一提交 `e3f9b1a` 完整还原（C09 已用字节与 SHA-256 核实还原到位）。

- 风险：若以 **merge 提交**方式并入 `main`，含缺陷的 `7b58ed6` 将成为
  从 `main` 可达的历史提交。任何按 commit 检出该点的构建（二分排查、历史复现、
  按 SHA 拉取）都会拿到 CRC 有缺陷的 `Libraries/OTA/ota_ble_frame.c`。
- 建议（供主会话收口时选择）：优先 **squash-merge**，使 `main` 只出现一个净效果提交；
  若确需保留提交粒度，则必须在收口证据中显式登记 `7b58ed6` 为「刻意注错、
  已由 `e3f9b1a` 还原、禁止单独检出使用」。
- 定性：属**收口策略**问题，不在本卡验收字段内，故未写为判据。

---

## 9. 校验器结论

```text
$ python -X utf8 -B Tools/acceptance/validate_bundle.py \
    --contract docs/acceptance-contracts/P3-6-v1.contract.json \
    --matrix docs/acceptance-contracts/P3-6-v1/P3-6-v1.evidence-matrix.json \
    --repo-root D:/github/my/E-Track
VALIDATION=PASS contract=P3-6-v1 round=P3-6-V1-FREEZE-20260902-01 overall=PASS
```

`--repo-root` 传的是本轮精确 Git worktree（`git rev-parse --show-toplevel` =
`D:/github/my/E-Track`，`HEAD` = `a9cf6f7fb0802059b52b67225851260e81728f90`）。
校验器从该 worktree **重新枚举并逐个读取**三个 profile 的真实文件、复核每个
`artifact.path` 与 `evidence_hashes` 的路径/大小/SHA-256——manifest 仅自洽不算通过。
矩阵含 `REUSED` 时才需要 `--previous-*` 参数；本轮无复用，故未传。

---

## 10. 评分（94 / 100）

**技术维度（48 / 50）**

- 接线正确性 20/20：命令序列逐行全等、纯 2 行增量、触发段未动、无验收脚本混入。
- fail-closed 有效性 18/20：六类吞码模式零命中，且有真实红运行 + 步骤级归因 +
  同提交对照运行三重证据。扣 2 分：步骤名漂移使 CI 失败时的归因可读性下降（发现 1）。
- 测试有效性 10/10：本地复算与 CI 标记逐字一致，排除弱化版测试与环境特有产物两种可能。

**战略维度（46 / 50）**

- 需求匹配 20/20：完全落在 P3-6 卡冻结任务源上，未自拟门槛，未越卡改产品代码。
- 范围与红线 18/20：20 条红线零 diff、产品源字节级还原、改动集全在授权分层。
  扣 2 分：注错提交仍在分支历史，收口方式若选错会把缺陷带进 `main` 可达历史（发现 2）。
- 治理一致性 8/10：合同/矩阵/manifest/校验器闭环完整，看板无哈希自指。
  扣 2 分：本卡不可避免地使已冻结的 P3-1-v2 Production 指纹漂移（DEV-3），
  虽已如实声明并按规约不回改，但仓库内确实同时存在两份对同一 `top_file` 的不同指纹记录，
  后续读者需依赖本报告才能理解其成因。

**综合 94 / 100，建议：通过。**（≥90 分且建议「通过」→ 确认通过。）

---

## 11. 收口待办（主会话执行，验收会话不得代劳）

1. 本轮新增的未跟踪文件需入库：`docs/acceptance-contracts/P3-6-v1.contract.json`、
   `docs/acceptance-contracts/P3-6-v1/**`、`tests/ota/p3_6_verify_*.py`（4 个）、
   本报告、`.claude/verification-report-p3-6.md`；以及两个脏文件
   `.gitattributes`（4 行 `-text` 护栏）与 `PLAN-OTA-EXEC.md`（状态回写）。
2. 合并方式按 §8 发现 2 择一，并把选择结果写入收口证据。
3. 合并后按 `AGENTS.md` §「Git / Worktree 收口规约」完成闭环：
   `git fetch --prune origin` → 定位实际检出 `refs/heads/main` 的主 worktree →
   `git merge --ff-only origin/main` → 核对 `HEAD` 与 `origin/main` 一致且无
   ahead/behind。仅更新 `origin/main` 引用不等于本地 `main` 已同步。
4. `.gitattributes` 的 `-text` 护栏必须与证据包同批入库：本机
   `core.autocrlf=true`，纯 LF 的 profile 成员若无护栏，真实检出会使冻结指纹打红。
   `/docs/acceptance-contracts/** -text` 已在既有第 19 行覆盖本证据包。
