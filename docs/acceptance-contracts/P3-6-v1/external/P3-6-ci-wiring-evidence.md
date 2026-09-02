# P3-6 CI 接线（批次 2）证据

- 日期：2026-09-02
- 任务卡：`PLAN-OTA-EXEC.md` §6 `P3-6 BLE 帧层测试 CI 接线`
- 认领：Claude(实现会话) / 2026-09-02
- 基线 HEAD：`ded14e8cb476a98191bcaca2d9b83be71471f044`（批次 1 治理变更之上）
- 前置：`docs/ota-exec-notes/P3-6-governance-change.md`（批次 1）

本文件承载本批次全部哈希（`docs/ota-exec-notes/` 不属任何 manifest profile，
登记哈希指纹中性；已由批次 1 实测确认）。

## 1. 动手前置：`tests/ota/p3_1_verify_*.py` 分类裁定

任务卡「目标」明确要求先在卡内定义这 7 个脚本属「验收工具」还是「产品回归」，
并据此决定是否一并接入，**不得默认全接**。裁定结果已回写任务卡「分类裁定」行。

### 1.1 结构性绑定 P3-1 单轮状态 → 验收工具，不接入（5 个）

| 脚本 | 不可接入的结构性原因 |
| --- | --- |
| `p3_1_verify_artifacts.py` | 把 P3-1 该轮申报的 9 个产物 SHA-256 硬编码为待验证输入；任何后续提交都会改变产物字节，接入即长期红 |
| `p3_1_verify_command_fidelity.py` | 与 P3-1 证据包内冻结日志逐字节比对；绑定该轮证据包，且需重跑冻结命令 |
| `p3_1_verify_mutation.py` | 向 `.cache` 源码副本注入缺陷并重编译，分钟级开销；其目的是证明**该轮** harness 鉴别力（验收合同 §7），不是持续回归 |
| `p3_1_verify_production_binary.py` | 从 `MDK-ARM_F435/cmake-generated/build-gcc-release` 的生产 ELF 与链接 map 取证；CI 构建目录为 `/tmp/etfw`，路径前提不成立 |
| `p3_1_verify_rx_ring_budget.py` | 需要同一本地生产构建目录下的 `compile_commands.json` 反读实际展开值，同上 |

### 1.2 内容上确实耐久 → 性质属产品回归，但本卡仍不接入（2 个）

`p3_1_verify_contract_alignment.py` 与 `p3_1_verify_text_isolation.py` 经实测可脱离
构建产物独立运行：

```
$ python tests/ota/p3_1_verify_contract_alignment.py
=== 契约漂移项 = 0 / 核对项 = 47 ===
P3_1_CONTRACT_ALIGNMENT=PASS drift=0 checks=47      (exit 0)

$ python tests/ota/p3_1_verify_text_isolation.py
=== 失败项 0 ===
P3_1_TEXT_ISOLATION=PASS cases=3 transparent=0 trace_points=1 sink_guard=True   (exit 0)
```

按性质它们属「产品回归」：前者锁定冻结契约 §5 表与 `ota_ble_frame.h` 宏的一致性，
后者锁定文本协议与二进制帧的隔离接线。**但本卡不接入**，理由不是它们跑不动，而是
接入会造成一个静默缺口：

- 现有 `paths` 触发器为 `tests/ota/test_ota_*.c` 与 `tests/ota/test_ota_*.py`；
- `p3_1_verify_*.py` 的文件名**不匹配**该模式；
- 于是「修改这两个门禁脚本本身」不会触发 `MCU Firmware Build`，形成
  「改门禁却不跑门禁」的盲区。

要正确接入必须连同触发器一并处理（或改名脱离 `p3_1_` 轮次前缀），属独立范围，
另立卡执行。本卡按「不得默认全接」的要求止步于裁定。

## 2. 接线改动

`.github/workflows/firmware-build.yml` 的 `Test Boot fw_header validator vectors`
步骤（`set -euo pipefail`）末尾新增两行：

```diff
@@ -193,6 +193,8 @@ jobs:
           python3 tests/ota/test_ota_staging.py
           python3 tests/ota/test_ota_package.py
           python3 tests/ota/test_ota_patch.py
+          python3 tests/ota/test_ota_ble_frame.py
+          python3 tests/ota/test_ota_ble_session.py
```

- `git diff --numstat` = `2 0`，纯新增，无其他改动。
- 触发器无需改：`paths` 已含 `tests/ota/test_ota_*.c` 与 `tests/ota/test_ota_*.py`，
  缺的确实只是执行那两行（与 P3-1 验收发现的描述一致）。
- 文件行尾为混合（CRLF=245 / bareLF=263），测试步骤区为裸 LF。因此改动通过
  `.cache/p36/edit_batch2.py` 字节级插入两条裸 LF 行，并断言
  `CRLF 不变 / bareLF 恰好 +2`，避免行尾归一化混入伪变更。
- 变更后：21482 B，CRLF=245，bareLF=263，
  SHA-256 `166053e2804df785d1733e9855f00be074bc5c5188bafe662c8cfdd39eb1f0a3`
- YAML 合法性：`yaml.safe_load` 通过，`jobs = ['build', 'register-cloudflare']`。

## 3. 看板回写

`PLAN-OTA-EXEC.md` 变更后 394813 B，CRLF=706（+1），bareLF=244（不变），
SHA-256 `8373722ea4824256e2dc1f959486f7e9675d5c0e0e6183a818ce19b4c0c5d7da`；
含批次 1 在内 `git diff --numstat` = `11 7`（批次 2 净增 `2 1`）。

批次 2 的 4 处改动：

1. 任务卡状态行：`待办` → `进行中`，认领填 `Claude(实现会话) / 2026-09-02`。
   状态取值仍在 §0 第 10 条钉死的四值内。
2. 任务卡新增「分类裁定」行（§1 的结论）。
3. 任务卡证据行：由 `—` 改为指向本文件与批次 1 笔记。
   该替换按卡块范围限定执行（`- 证据: —` 在全文多处出现，不可全局替换）。
4. §10 会话日志：**续写**批次 1 已有的同会话条目，不新开行——看板要求
   「每会话一行」，而两个批次出自同一会话。

## 4. 本地验证

### 4.1 治理门禁

```
$ python tests/ota/test_acceptance_bundle.py
Ran 65 tests in 44.785s

OK
```

### 4.2 CI 测试步骤全序列本地复跑

以 `set -euo pipefail` 复跑接线后的 8 条命令，整体退出码 0，且两个 marker
出现在 stdout（即验收要求「CI 运行日志中可见实际执行输出」的本地对照）：

```
P3_1_BLE_FRAME=PASS checks=39 failures=0
P3_1_BLE_SESSION=PASS checks=105 failures=0
步骤整体退出码=0
```

**环境说明（不影响 CI）**：本机 `python3` 是 Windows 应用执行别名，任何脚本都返回
空输出 `rc=49`，并非真解释器；本地复跑改用 `python`。CI runner 为 ubuntu，
`python3` 是真解释器，且该步骤既有 6 行今日仍为绿，故 `python3` 的写法与相邻行
完全一致、无需改动。

### 4.3 fail-closed 本地预检（缺陷注入 → 变红 → 逐字节还原）

对被接线的产品源 `Libraries/OTA/ota_ble_frame.c` 做临时缺陷注入，验证接线命令
确有鉴别力。脚本以「先记 SHA-256 → `finally` 还原 → 复算并断言相等」保证工作区安全：

```
原始 Libraries/OTA/ota_ble_frame.c  size=11729
     sha256=07b20f99c37910ccec0cdc8223cea58e7823451a9198f952c30ec98e1003e02a
基线 rc=0 | P3_1_BLE_FRAME=PASS checks=39 failures=0
注入(CRC 累加 ^= 改为 |=) rc=1 | === summary: 39 checks, 13 failure(s) ===
还原后 sha256=07b20f99c37910ccec0cdc8223cea58e7823451a9198f952c30ec98e1003e02a  一致=True
```

`git diff --stat -- Libraries/ USER/` 为空，产品源零改动。

**这只是预检，不是任务卡要求的反证。** 卡内验收要求的是「接线确实生效」，
即缺陷必须让 **workflow** 变红，而非只让本地命令变红。该证据见 §6，需推送后补齐。

## 5. 对 P3-1 冻结合同的影响（如实申报）

`.github/workflows/firmware-build.yml` 是 Production profile 的 `required_paths`
成员（任务卡「注意」行已预先记载）。接线后复跑 P3-1 冻结合同校验器：

```
$ python Tools/acceptance/validate_bundle.py     --contract docs/acceptance-contracts/P3-1-v2.contract.json     --matrix docs/acceptance-contracts/P3-1-v2/P3-1-v2.evidence-matrix.json     --repo-root .
ERROR: input manifest worktree length mismatch: .github/workflows/firmware-build.yml
ERROR: input manifest worktree SHA-256 mismatch: .github/workflows/firmware-build.yml
ERROR: input manifest worktree length mismatch: tests/ota/test_acceptance_bundle.py
ERROR: input manifest worktree SHA-256 mismatch: tests/ota/test_acceptance_bundle.py
ERROR: input manifest is missing worktree files for Governance: docs/ota-prompts/prompt-P3-6-implementation.md
ERROR: input manifest worktree length mismatch: PLAN-OTA-EXEC.md
ERROR: input manifest worktree SHA-256 mismatch: PLAN-OTA-EXEC.md
VALIDATION=FAIL errors=7
```

由批次 1 的 `errors=5` 增至 `errors=7`，增量恰为 `firmware-build.yml` 的
length + SHA-256 两条，**无任何未申报的夹带**。判定同批次 1：属已确立的治理漂移
模型，P3-1 轮次的可复现性由其收口锚定提交承载，已 PASS 的轮次不被改判。

P3-6 将携带自己新 `task_id` 的独立验收合同，不回改 P3-1 的合同或证据矩阵。

## 6. CI 运行证据与 fail-closed 反证（已取得）

工作流触发条件为 `push: branches [main, master]` 或
`pull_request: branches [main, master]`，特性分支单纯推送**不会**触发，故反证必须
在 PR 上取得。实际执行：分支 `ota/p3-6-ci-wiring` → PR #14 → 绿、红、绿三次运行。

`paths` 触发器已含 `.github/workflows/firmware-build.yml` 本身（实测读取该文件的
`on` 段确认），故仅改 workflow 的提交也能触发；注错提交改的是
`Libraries/OTA/ota_ble_frame.c`，命中 `Libraries/**`。

### 6.1 三次运行总表

| # | commit | run id | `MCU Firmware Build` | `acceptance-governance` | 用途 |
| - | ------ | ------ | -------------------- | ----------------------- | ---- |
| 1 | `0a97b98` | 33620407886 | **success** 1m7s | success 45s | 基线绿：证明两套测试确实在 CI 上执行 |
| 2 | `7b58ed6` | 33621049995 | **failure** 1m6s | success 44s | 反证：注入缺陷后 workflow 变红 |
| 3 | `e3f9b1a` | 33621403637 | **success** 55s | success 47s | 还原后恢复绿 |

### 6.2 基线绿（run 33620407886）

`Test Boot fw_header validator vectors` 步骤的 `Run` 分组回显确认 8 条命令均已下发
（`set -euo pipefail` + 8 条 `python3 tests/...`，末两条为本卡新增）。该步骤 stdout
内的全部测试标记，逐行原样摘录：

```text
P1_1_FW_HEADER_VECTORS=PASS cases=16
=== summary: 19 checks, 0 failure(s) ===
P1_1_BOOT_PROTOCOLS=PASS
P1_3_STATE_MACHINE=PASS checks=96 failures=0
=== summary: 48 checks, 0 failure(s) ===
P2_1_STAGING=PASS checks=48 failures=0
P2_2_PACKAGE=PASS checks=102
P2_3_VECTOR_PREFLIGHT=PASS vendor_controls=11 oldpos_only=9 invalid_control=[0,0,0]
=== P3-1 BLE frame and ring tests ===
=== summary: 39 checks, 0 failure(s) ===
P3_1_BLE_FRAME=PASS checks=39 failures=0
=== P3-1 BLE session tests ===
=== summary: 105 checks, 0 failure(s) ===
P3_1_BLE_SESSION=PASS checks=105 failures=0
```

卡内验收判据要求的两个标记 `P3_1_BLE_FRAME=PASS checks=39` 与
`P3_1_BLE_SESSION=PASS checks=105` 均以**实际执行输出**形式出现，非文本 diff 推定。
该步骤 env 回显 `BUILD_DIR: /tmp/etfw`，与 §1 裁定中「CI 构建目录不是
`build-gcc-release`」的判断一致。

### 6.3 fail-closed 反证（run 33621049995）

注入的缺陷与 §4 本地预检使用的完全相同：`Libraries/OTA/ota_ble_frame.c` 的
CRC-16 循环 `crc ^= ` 改为 `crc |= `。选它的理由是可编译、不破坏固件构建，故失败
必然落在测试步骤而非编译步骤，才能证明是**测试**而不是编译器发现了问题。
文件长度不变（11729 B），SHA-256 由
`07b20f99c37910ccec0cdc8223cea58e7823451a9198f952c30ec98e1003e02a` 变为
`58abd1ec5e1cd49bee03103709232a7a923d43f97d916eb260dea450596cbb67`。

实际观测（`gh run view --json jobs` 与 `--log-failed`）：

- 失败步骤 = **第 10 步 `Test Boot fw_header validator vectors`**，即被本卡接线改动的
  那一步，不是别的步骤。
- 失败发生在新接入的第一行：`=== P3-1 BLE frame and ring tests ===` 下
  `=== summary: 39 checks, 13 failure(s) ===`，随后
  `subprocess.CalledProcessError: Command '[...test_ota_ble_frame]' returned
  non-zero exit status 1`，步骤以 `##[error]Process completed with exit code 1` 结束。
- 该步骤带 `set -euo pipefail`，首个失败即终止，故第二行
  `test_ota_ble_session.py` 未执行 —— 与注错提交里预先写下的预期一致。
- 同一步骤内位于新增两行**之前**的 6 条命令全部照常 PASS
  （`P1_1_*`/`P1_3_*`/`P2_1_*` 标记齐全），排除「环境整体坏掉」这种伪反证。
- 13 条变红用例名：CRC16-CCITT-FALSE 校验值、ABORT/BEGIN/END/DATA 四类帧
  round-trip、session/seq 全 16 位回显、交织噪声后顺序解析、截断帧后重同步、
  重复 A5 起始、文本环绕二进制帧、`A5 A5 5A` 透传、NULL sink 丢文本 —— 与 §4
  本地预检的 13 条同源同数。
- **同一提交上 `acceptance-governance` 仍为绿（success 44s）**。这条对比很关键：
  它说明这个产品缺陷不会被既有的治理门禁抓到，鉴别力只可能来自本卡新增的两行；
  接线之前该缺陷可以一路绿灯合入。

### 6.4 还原后恢复绿（run 33621403637）

用 `git revert` 还原，还原后复算 `Libraries/OTA/ota_ble_frame.c` 的 SHA-256 为
`07b20f99c37910ccec0cdc8223cea58e7823451a9198f952c30ec98e1003e02a`，与注错前逐字节
一致；`git diff --cached main -- Libraries/ USER/ boot/ MDK-ARM_F435/` 为空，即相对
`main` 产品源码零差异。run 33621403637 重新出现
`P3_1_BLE_FRAME=PASS checks=39 failures=0` 与
`P3_1_BLE_SESSION=PASS checks=105 failures=0`。

PR 历史里保留了注错提交 `7b58ed6` 与还原提交 `e3f9b1a`（用户已知悉并同意留痕），
不做历史改写：反证的可复核性依赖这两个提交及其对应 run 仍可访问。

### 6.5 结卡边界

CI 侧证据已完整，但按 `AGENTS.md` OTA 执行规约 §3，验收命令须由**非实现会话**执行，
实现会话不自验收；且 P3-6 须自带新 `task_id` 的独立验收合同（不得复用或回改
P3-1-v2）。因此本卡状态保持「进行中」，由后续独立验收会话裁定。

## 7. 边界声明

- 本批次改动 3 个文件：`.github/workflows/firmware-build.yml`（+2 行）、
  `PLAN-OTA-EXEC.md`（卡状态/裁定/证据/日志）、本证据笔记（新增）。
- 同会话的批次 1（治理变更）另改 4 个文件，与本批次分列两个提交，清单与实测见
  `docs/ota-exec-notes/P3-6-governance-change.md`；本笔记只对本批次负责。
- 两批共用同一份看板文件，落地时用 `.cache/p36/board_split.py` 在两个目标字节
  状态间切换，切换以 size + SHA-256 + CRLF/裸 LF 计数双向硬断言，实测往返逐字节
  可逆（批次 1 = 393305B/CRLF 705，批次 2 = 394813B/CRLF 706）。
- 未改动任何产品源码（缺陷注入已逐字节还原并复算 SHA-256 确认）。
- 未改动 P3-1 的合同、证据矩阵或任何既有验收资产。
- 未改动 `paths` 触发器；`p3_1_verify_*.py` 一个都未接入。
- 6 个刻意排除的未跟踪文件保持未跟踪。
- 临时脚本 `.cache/p36/edit_batch2.py`、`.cache/p36/local_failclosed.py`、
  `.cache/p36/board_split.py` 落在
  仓库内已忽略目录，不入库。
