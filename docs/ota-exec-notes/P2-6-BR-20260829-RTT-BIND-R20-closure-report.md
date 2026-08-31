# P2-6-BR-20260829-RTT-BIND R20 收口报告（证据包成形，不改判定）

- 日期：2026-08-30
- 会话：R20 收口 agent（非实现方、非验收方）
- 分支/worktree：`p2-6-implementation-20260819` @ `D:/github/my/E-Track`
- 前置判定：独立验收会话已于 2026-08-30 判 **PASS**（本会话不改变任何判定）
- 硬件动作：**零**（未 J-Link、未烧录、未 RTT、未重跑 harness）
- git：**未 commit / 未 push / 未 merge**（交主会话收口）

## 1. 三处文档缺陷更正（仅改 R19 证据文档本身）

被改文件：`docs/ota-exec-notes/P2-6-BR-20260829-RTT-BIND-R19-implementation-evidence.md`
（UTF-8 无 BOM、纯 LF；未改产品代码，未改 `PLAN-OTA.md` / `docs/ota-binary-contracts.md`）。

### D1 §7.1 `binding.gdb` SHA-256 尾部

| | 内容 |
|---|---|
| 原文 | `binding.gdb`：`BD3B5445...121AD8`（缩写，尾部错） |
| 实读复算 | `BD3B5445C53096F01C5FDDFDA4AF8DA332C4D0FB25E4E2F051780D05702121D8`（尾部 `2121D8`） |
| 改后 | 表格给出完整 SHA-256 与字节数 103655 |

复算来源：根 `-18` 的 `scripts/binding.gdb` 逐文件 SHA-256（本报告 §3 的 `CMD-GDB-SHA`）。

### D2 §3.3 冒烟根 `-20` 不存在

原缺陷叙述**保留未删**（"冒烟 A 第三轮（根 -20）capture PASS 后 postcheck 报
`SRAM changed outside the four-byte Up0 RdOff word`"），其后追加更正块，如实标注：

- 根 `-20` 已被后续冒烟迭代覆盖/未留存，磁盘现存根为 `-16/-18/-19/-21/-22/-23`，
  该现象无法再由 `-20` 自身复算；
- 缺陷与修复由两条独立证据链坐实：① 离线变异测试 `PostcheckSemanticsTests` 三例；
  ② 根 `-21`、`-23` 两轮真机全链复现修复后语义（postcheck PASS、控制块 RdOff 字外零变化）；
- 明确声明"不新增、不推定、不编造任何证据根"。

### D3 §7.1 6 个 `readback-gate-*.gdb` 缺字节数与 SHA-256

原文只给形状计数（147 dump + 294 DHCSR + 1 行 wdt 暂停），现补齐实读值：

| 生成脚本 | 字节 | SHA-256 |
|---|---|---|
| binding.gdb | 103655 | BD3B5445C53096F01C5FDDFDA4AF8DA332C4D0FB25E4E2F051780D05702121D8 |
| binding-post.gdb | 3051 | 90DF212F4BBB73DA071B18E629B7D798CAF320AB3BD28A846171BB0BFDB117E9 |
| readback-gate-pre-a.gdb | 84573 | BE33110E49E3EA890F8B5E927F9965213C6B3DCA3A239184256C69F96FCE331D |
| readback-gate-pre-b.gdb | 84573 | 4786363036AA637FF4042A7A8229471C172EFE47EBEB7BD393717239B4DE6C3F |
| readback-gate-pre-c.gdb | 84573 | 82921E9548861E3D61E89E638761B1D1EAADD73625EF86D3FAE8F986345BE55C |
| readback-gate-post-a.gdb | 84870 | 7093742584419F90D83A3808A0641880D718E0DDD3B553A0FCA2DCB39AF978E1 |
| readback-gate-post-b.gdb | 84870 | 331537AF3BAC80A6BC8B5F8CABEB1C4E331EE63C2D86DAF5A328E60D9C1C5588 |
| readback-gate-post-c.gdb | 84870 | 123A7C46E7C25590A821CDCB2A79DB4AC739DB7D851AD38294F2D3655A8B0E16 |

`binding-post.gdb` 3051 B 复算与原文一致（原文该行无误）。三处更正均在文档内加了
"更正（R20 收口，2026-08-30；来源：…）" 标注；§9 另加一条状态更新块，指向本轮冻结的
合同与矩阵，并声明"合同在验收之后冻结"已作为流程偏离在合同内登记。

## 2. 冻结的验收合同与证据矩阵

| 项 | 路径 | 字节 | SHA-256 |
|---|---|---|---|
| 合同 | `docs/acceptance-contracts/P2-6-v1.contract.json` | 17416 | `330F3A5AFC668AB2DC061E9AFF261600F1442A5A26389954F0174F959A98DBC8` |
| 证据矩阵 | `docs/acceptance-contracts/P2-6-v1/P2-6-v1.evidence-matrix.json` | 14647 | `4D70BA806C7FC30BB814B01C89E66DBEBB3E42886AB26A6F2E79E41AF4DB4D72` |
| Production manifest | `…/P2-6-v1/manifest-production/source-manifest.json` | 573514 | `047E8C0E32CC99AA586F61DBB88686EB19F6301524BCA29E996D5D2B1AFFCDC7` |
| Validation manifest | `…/P2-6-v1/manifest-validation/source-manifest.json` | 23158 | `D03EB877F7E27CE98F4C41B564210E94500398E95DF0D7B5DC38175B926503A8` |
| Governance manifest | `…/P2-6-v1/manifest-governance/source-manifest.json` | 4505 | `F872002B59B453BD51988F7312487CCD1443FE33C2482ECAFAD4ACFC8B255198` |

- `task_id = P2-6`（沿用看板既有卡号，未新造）；`contract_id = P2-6-v1`，`version = 1`，
  `parent_contract_sha256 = null`（`docs/acceptance-contracts/` 此前只有两个模板，无 P2-6 历史合同）。
- 三类 manifest 的稳定 `ManifestSHA256`：Production `F173B678…`（2912 文件）、
  Validation `8837FE99…`（128 文件）、Governance `FFC61103…`（23 文件）。profile 范围
  完全由 `Tools/provenance/manifest_profiles.json` 定义，枚举与稳定哈希直接复用
  `validate_bundle.py` 的 `_collect_profile_records` / `_manifest_text_bytes`（未改校验器）。
- 判据 9 条，全部 `EXECUTED` + `PASS`，**零 `REUSED`**；`previous_matrix_sha256` /
  `rerun_plan_path` / `rerun_plan_sha256` 均为 `null`。
  判据：`HW-RTT-BINDING`、`HW-CAPTURE-PAYLOAD`、`HW-POSTCHECK-RDOFF`、`HW-HALT-GATE`、
  `HW-IMAGE-AUTHORITY`、`HW-NO-FLASH-WRITE`、`PROC-WDT-PAUSE`、`PROC-NATURAL-EXIT`、
  `PROC-EVIDENCE-DOC-ACCURACY`。
- 证据包 `docs/acceptance-contracts/P2-6-v1/` 共 28 个文件、约 3.2 MB：21 个 artifact
  （8 个结构化 JSON 结果、3 个原始日志、8 个二进制快照 + 根封存 manifest + 更正后 R19 文档副本）
  + 3 组 manifest（json/txt）+ 矩阵。903 KB 的 server log 与 6 份 ~207 KB 的 readback server log
  未纳入包体，其完整性仍由根 `-18` 的 `manifest.json`（`ART-ROOT-MANIFEST`，绑定根内全部文件）承载。
- `CMD-ACCEPT-RUN` 的 `exit_code: 0` 非臆断：`run_recovery_binding.py` 在根 manifest 存在时
  返回 `run_binding.py` 的返回码，而 `run_binding.py:1860` 为
  `return 0 if classification == "RTT_CHANNEL_BINDING_VERIFIED" else 1`，
  `result.json` 记录的 classification 正是该值。该推导已写入矩阵命令记录的 notes。

### 已登记偏离（合同 `authorized_deviations`）

| ID | 类型 | 内容 |
|---|---|---|
| DEV-1 | 已授权硬件偏离 | 每 halt 会话一次 `monitor WriteU32 0xE0042008 0x00001000`（DEBUG_WDT_PAUSE）；非 flash、断电即失、不改镜像字节，server log 回显 count==1 fail-closed 校验 |
| DEV-2 | 已授权硬件偏离 | capture 阶段用 `Stop-Process` 停止 `JLinkRTTLogger` 并验证零残留（该工具无自然退出，AGENTS.md 规定流程；GDB/server 仍自然退出） |
| DEV-3 | 流程偏离（如实登记，不掩饰） | 本合同在独立验收判定之后冻结，而非验收前冻结；沿用 R17 以来既有流程，后续 P2-6 轮次应改为验收前冻结 |

### 合同范围声明（防越界解读）

合同 `scope` 字段明确：只覆盖 RTT 通道绑定轮次（根 `-18`，audit-id
`P2-6-BR-20260829-RTT-BIND-R19-03`）。P2-6 卡内 C1/C2、C4-C7、C14 以及升级态 RAM 峰值
实测回填**不在本合同范围**，仍为 `NOT_OBSERVED`。

## 3. 校验（任务 3）

```
python Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P2-6-v1.contract.json --matrix docs/acceptance-contracts/P2-6-v1/P2-6-v1.evidence-matrix.json --repo-root D:/github/my/E-Track
```

输出：

```
VALIDATION=PASS contract=P2-6-v1 round=20260830-R20-CLOSURE overall=PASS
EXIT=0
```

首轮曾报 `contract.artifacts contains unreferenced ids: ART-PRECALL-JSON`（exit 1），
修复方式是把 `precall.json` 正确挂到 `HW-RTT-BINDING`（会话 1 的 `precall_pass` 标记确由它佐证），
**未改校验器、未删判据、未放宽门槛**。

另一条只读复算命令（判据 `PROC-EVIDENCE-DOC-ACCURACY` 绑定，输出即
`artifacts/logs/generated-gdb-sha256.txt`，exit 0）：

```
python -c "import hashlib,pathlib
for p in sorted(pathlib.Path('.cache/p2-6-rtt-binding-20260829-18/scripts').glob('*.gdb')):
    print(f'{p.name} {p.stat().st_size} {hashlib.sha256(p.read_bytes()).hexdigest().upper()}')"
```

## 4. 看板回写（任务 4）

`PLAN-OTA-EXEC.md` 存在混合 EOL，全部改动用 Python 字节级 `split(b'\n')`/`join` 完成，
未引入伪 diff（改后 UTF-8 解码校验通过，文件 893→894 行）：

| 行号 | 改动 |
|---|---|
| 555（改） | 卡状态 `状态: 进行中` → `状态: 独立验收通过`，行尾追加本轮判定摘要（正式验收根、audit-id、分类、14 marker、两会话 rc=0）、合同与矩阵路径，并显式声明"本状态仅覆盖该 RTT 通道绑定轮次"，C1/C2、C4-C7、C14 仍 `NOT_OBSERVED` |
| 893（新增） | §10 会话日志追加一行（2026-08-30，R20 收口 agent，三处文档更正 + 合同/矩阵冻结 + 偏离登记 + 未动产品代码/冻结契约、未 commit/push），行尾 `\r` 与该节 CRLF 风格一致 |

## 5. 边界自查

- 写入全部落在项目根内：`docs/ota-exec-notes/`、`docs/acceptance-contracts/`、
  `PLAN-OTA-EXEC.md`、`.claude/build_p2_6_bundle.py`（生成脚本，非 manifest profile 范围）。
- 封存根 `-14/-15/-18/-21/-23` 全程**只读**（仅 `shutil.copyfile` 读出与 SHA 复算）。
- 未改产品代码、未改冻结契约、未改 `Tools/acceptance/validate_bundle.py`
  与 `Tools/provenance/manifest_profiles.json`。
- 零硬件动作、零 git 写操作。

## 6. 已知设计问题（本轮不处理）

Governance profile（`Tools/provenance/manifest_profiles.json`）通过 `top_files`
收录活文档 `PLAN-OTA-EXEC.md`。该文件是持续推进的 OTA 看板，任何后续轮次回写
状态行都会改变其字节数与 SHA-256，而合同 `input_groups.governance.manifest_sha256`
绑定的正是该枚举的稳定哈希。后果：本证据包只能在「PLAN-OTA-EXEC.md 恰为本包
生成时字节状态」的提交点复验通过；此后任何看板推进（哪怕与 P2-6 无关的卡）都会
使 `validate_bundle.py` 报 `input manifest worktree SHA-256 mismatch: PLAN-OTA-EXEC.md`
而复验红。2026-08-30 验收方单独修看板状态行即触发此问题（EXIT=1），改动已还原，
随后由 R20 补正会话以「改看板 + 同步重生成 Governance manifest + 重绑合同哈希」
的方式原子闭环（本轮校验器 EXIT=0）。

是否将活文档移出 Governance profile（或改用内容快照代替活文件枚举）属 profile
范围裁定，交非实现裁定会话决定；本轮按硬边界不自行更改 profile 定义与校验器。
