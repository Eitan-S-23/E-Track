# P2-6-SD-R5 阶段 0 独立复核报告（2026-08-30）

- 复核会话角色：独立复核 agent（未参与实现，未参与验收；不接受实现会话任何口头结论，全部结论以本会话实测为准）
- 复核对象：R5 阶段 0（driver 两段式采集通道离线重构）实现声明
  `docs/ota-exec-notes/P2-6-SD-R5-phase0-offline-evidence-2026-08-30.md`
- 授权依据：派单裁定 `P2-6-BR-20260830-SD-R5-01=AUTHORIZED_RESUME`
  （`docs/ota-exec-notes/P2-6-SD-R5-dispatch-ruling-2026-08-30.md` §4.2 白名单 =
  仅 `tests/ota/p2_6_rtt_ota_driver.py` 与 `tests/ota/test_p2_6_rtt_ota_driver.py`）
- 复核指令：`.claude/prompt-P2-6-SD-R5-independent-review.md`（七项机械清单）
- 复核环境：分支 `p2-6-implementation-20260819`，HEAD `d27200d`；
  本会话零硬件（未启动 J-Link/GDB server/RTT logger/OTA，未写 SD/Flash/目标内存）、
  零 git 写操作；除本报告与指令第 5 项授权的 prepare-only 项目内临时产物外未写任何文件。

## 复核 1：哈希复算 — **PASS**

方法：Python `hashlib` 直接读字节复算（不引用实现会话任何运行结果）。

| 文件 | 实测字节数 | 实测 SHA-256 | 预期（证据 §1"修改后"） | 比对 |
|---|---|---|---|---|
| `tests/ota/p2_6_rtt_ota_driver.py` | 70942 B | `1B092AF294850AC353D48116D9205A5C1F9E9EF7476D51425891338735A64C56` | 70942 B / `1B092AF2…5A64C56` | 一致 |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | 53997 B | `411E01A7C866C74E440B43F97695602B7D2BF0DC6037A1EE2EEBBCFFE51CD5FB` | 53997 B / `411E01A7…E51CD5FB` | 一致 |

## 复核 2：diff 范围审计 — **PASS**

`git status --short` 实测 tracked 改动（M）恰 3 个文件：

```text
 M PLAN-OTA-EXEC.md
 M tests/ota/p2_6_rtt_ota_driver.py
 M tests/ota/test_p2_6_rtt_ota_driver.py
```

`git diff --stat`：`PLAN-OTA-EXEC.md +4 行`，driver 与单测两文件。逐行核对
`git diff PLAN-OTA-EXEC.md`：新增 2 行为任务卡登记行（P2-6-SD-R5 派单裁定行 +
P2-6-SD-R5 阶段 0 离线实现完成行）、2 行为 §10 会话日志行，全部为登记性追加，
无既有行改动，属指令允许范围。

其余 p2_6 harness 文件工作区与 HEAD 哈希逐一复算，全部 `SAME`（零改动）：

| 文件 | 字节数 | 工作区=HEAD |
|---|---|---|
| `tests/ota/p2_6_rtt_sd_uploader.py` | 26870 B（`88253A46…FDB61`，与证据声明一致） | 是 |
| `tests/ota/p2_6_rtt_sd_preflight.py` | 8013 B | 是 |
| `tests/ota/p2_6_rtt_transport_qualifier.py` | 13403 B | 是 |
| `tests/ota/test_p2_6_rtt_sd_uploader.py` | 8335 B | 是 |
| `tests/ota/test_p2_6_rtt_sd_preflight.py` | 4173 B | 是 |
| `tests/ota/test_p2_6_rtt_transport_qualifier.py` | 10537 B | 是 |

未跟踪文件如实登记（均非 tracked 改动）：`.claude/prompt-P2-6-SD-R5-independent-review.md`
（复核指令）、`docs/ota-exec-notes/P2-6-SD-R5-{dispatch-ruling,phase0-offline-evidence}-2026-08-30.md`
（裁定与证据文档）、`.claude/write_r5_{ruling,phase0}_board.py`（看板回写脚本），以及会话开始前
即已存在的 `.cache-cmake-time-test.cmake`、`.claude/cc_recover_s4.js`、`.claude/ccprobe_hash.js`、
`.claude/ccprobe_plan.js`（与本轮实现无关的既有残留）。

## 复核 3：fixture 重跑 — **PASS**（附环境性例外披露，见"异常"节）

本会话独立执行（`cd tests/ota` 后逐套运行，不引用实现会话结果）：

| 套件 | 预期 | 实测 | 结论 |
|---|---|---|---|
| `test_p2_6_rtt_ota_driver.py` | 38 项 OK | Ran 38 tests, 1.788s, **OK** | 符合 |
| `test_p2_6_rtt_sd_preflight.py` | 3 项 OK | Ran 3 tests, 0.181s, **OK** | 符合 |
| `test_p2_6_rtt_sd_uploader.py` | 7 项 OK | Ran 7 tests, 0.025s, **OK** | 符合 |
| `test_p2_6_rtt_transport_qualifier.py` | 4 项 OK | Ran 4 tests, 0.125s, **OK** | 符合 |
| `test_acceptance_bundle.py` | 65 项 OK | Ran 65 tests, 36.703s, **FAILED (failures=1)**：64 OK + 1 FAIL | 见下 |

唯一失败项 `GovernancePromptScopeTests.test_dispatch_prompts_do_not_live_outside_governed_dir`
（`test_acceptance_bundle.py:1043`）。本会话逐层定位其根因：

1. 该测试用 `git ls-files -co --exclude-standard -- *.md` 全仓枚举 .md（含未跟踪文件），
   判定"派单提示词必须位于 `docs/ota-prompts/` 下"；正则按卡号前缀
   （`prompt-(?:PRE|P\d+)…\.md`）识别派单提示词。
2. 失败输入恰为本复核的指令文件本身：
   `.claude/prompt-P2-6-SD-R5-independent-review.md`（文件名含 `P2-6` 卡号前缀且位于
   `.claude/`，命中 stray 规则）。
3. 本会话导入测试模块原始逻辑复现枚举：全部枚举 .md 共 287 个，stray 集合**恰好只有**
   该复核指令文件 1 个元素；排除该文件后 stray 为空集。即该测试的失败输入唯一且
   与被复核实现无关——若工作区不含此文件，此套件必为 65 项全 OK（其余 64 项实测已通过）。
4. mtime 时间链佐证：driver/单测最后修改 18:38/18:46 → prepare-check 产物 18:49 →
   证据文档落盘 18:51 → 复核指令文件落盘 18:59。实现会话声明"65 项 OK"的时点
   （≤18:51）该文件尚不存在，声明在其时点真实成立。

判定：该失败由复核派发方将指令文件放置在 `.claude/` 引起（触发仓库治理规则），不构成
两白名单文件的实质缺陷，故第 3 项判 PASS；但此治理发现已如实登记至"异常与披露"节。

## 复核 4：§40.6 五项修复门槛独立核验 — **PASS**（读代码本身，不采信文档自述）

对 `tests/ota/p2_6_rtt_ota_driver.py`（复核 1 哈希版）逐项读源码核验：

1. **socket connected ≠ payload ready** —
   `probe_rtt_telnet`（485-525 行）只做 TCP 连接 + 记录 SEGGER banner 到 rtt log，
   返回 `(connected, banner, error)`；docstring 显式声明"A successful TCP connect never
   means payload-ready"。`rtt_payload_ready` 在 `run_gdb_session` 初始恒 False（739 行），
   仅由 `run_two_phase_ota_session` 在 1446-1448 行以
   `rtt_pending_derived(derive ELIGIBLE) and rtt_drain_success(capture PASS)` 组合置位。✓
2. **banner-only/截断/缺失/socket 错误/超时/channel 未证实全部 fail-closed** —
   `classify_transport_session`（646-685 行）两级拆分实测确认：
   measurement 分支先 `RTT_PAYLOAD_FAIL`（666-680 行，derive/capture 层任一失败含
   `rtt_record_count != 1`、`rtt_matching_record_count != 1`、超时、socket EOF/error、
   capture_error），后 `RTT_POSTCHECK_FAIL`（681-682 行）。路径覆盖实测：
   telnet 连接失败→`RTT_NOT_READY`（779-782 行 raise）；非 SEGGER banner→
   `rtt_socket_error` + raise→`GDB_NOT_STARTED`（786-790 行）；空库存/banner-only→
   derive `EMPTY`→session_error"RTT pending inventory is empty"（1428-1429 行）；
   控制块截断/签名不符/环尺寸不符→`rtt_descriptor`/derive 异常（840-897 行）；
   channel 未证实→`rtt_channel_binding_verified = rtt_payload_complete`（1459 行）
   仅在全链闭合时为 true。✓
3. **有界采集 + 恰一条匹配 kind 完整记录** —
   derive 强制 `len(records)==1 and len(matching)==1`（913-920 行，重复/异 kind/截断
   均失败并回填 `record_count`/`matching_record_count`）；capture 以 pending 尺寸为界
   （`delivered >= len(pending)` 后 break，1004-1014 行），随后 settle 静默期
   （1019-1023 行）与终检（1025-1028 行）拒绝任何额外字节，`payload != pending` 即
   失败（逐字节一致）。✓
4. **GDB 非零优先于 payload 判定；server 强制收尾/端口残留 fail-closed** —
   `classify_transport_session` 顺序实测：`gdb_exit_code != 0 → GDB_FAIL`（655-656 行）
   位于 measurement/payload 分支（666 行起）**之前**；`run_two_phase_ota_session`
   1368-1374 行 `transport_ok = (session_error is None and gdb_exit_code == 0)`，
   不满足则 derive/capture/postcheck 一律不运行。`CLEANUP_FAIL`（657-665 行）覆盖
   server 未自然退出/terminate/kill/capture_stopped/端口未闭合；`run_gdb_session`
   822-834 行把端口残留、server 清理错误、强制收尾统一并入 session_error。✓
5. **负例 fixture 实际存在且有效**（在单测源码中逐一找到，且断言有真实鉴别力）：
   - 空库存/banner-only：`test_two_phase_rejects_empty_and_banner_only_inventory`（322 行）
   - 重复/异 kind：`test_two_phase_rejects_duplicate_and_wrong_kind`（330 行）
   - 截断：`test_two_phase_rejects_truncated_record`（342 行）
   - capture 超时/额外字节/不一致：`test_two_phase_rejects_capture_timeout_extra_bytes_and_mismatch`（349 行）
   - postcheck WrOff 变化/RdOff 停滞/越界字节：`test_two_phase_rejects_wroff_change_rdoff_stall_and_extra_cb_bytes`（376 行）
   - post 会话失败：`test_two_phase_post_session_failure_fails_closed`（392 行）
   - GDB 非零（有效 payload 仍 GDB_FAIL）：`test_gdb_nonzero_fails_even_with_valid_payload`（399 行）
   - binding 不自证：`test_two_phase_never_reports_binding_without_full_chain`（408 行）
   - socket 错误/非 SEGGER banner：`test_session_rejects_non_segger_banner`（843 行，
     mock JunkSocket 断言 `GDB_NOT_STARTED` 且 GDB 未启动）
   - readiness 失败不启动 RTT/GDB：`test_readiness_failure_never_starts_rtt_or_gdb`（890 行）
   - derive 8 项结构负例：`test_derive_rtt_pending_structural_failures`（1031-1083 行，
     bad_signature/bad_up_size/bad_pbuffer/bad_flags/bad_buffer_counts/bad_ring_size/
     wroff_out_of_range/rdoff_out_of_range 逐 subTest 断言 FAIL）
   - 环回绕库存正例：`test_derive_rtt_pending_wraparound_inventory`（1085 行）
   - postcheck 5 变体：`test_verify_rtt_postcheck_pass_and_failures`（1103-1150 行，
     PASS + WrOff 变/RdOff 停滞/消费量不符/越界字节/RdOff 字内合法变化）
   - logger mock 负例 3 组：`test_logger_capture_passes_on_byte_identical_payload` /
     `test_logger_capture_fails_closed_on_timeout_and_extra_bytes` /
     `test_logger_capture_fails_closed_on_early_exit_and_residuals`（1215-1249 行，
     含提前退出与残留进程 fail-closed）
   - 脚本静态断言 2 项：`test_generated_script_snapshots_rtt_while_halted_with_wdt_pause`
     （578 行，WDT 唯一 + 快照 dump 在 detach 前 + PASS marker 之后）与
     `test_post_snapshot_script_is_halt_wdt_dump_only`（615 行，零 continue/call/reset/
     loadbin/loadfile）。✓

## 复核 5：prepare-only 独立复跑 — **PASS**

命令（Git Bash 单行等价形式，含 MSYS 路径屏蔽前缀）：

```text
MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' python tests/ota/p2_6_rtt_ota_driver.py \
  --prepare-only --kind PATCH \
  --package-path "/P2-6-SD-R5-REVIEW-CHECK/review.etu" \
  --output-prefix p2-6-sd-r5-review-check
```

result JSON 实测（`.cache/p2-6-sd-r2/logs/p2-6-sd-r5-review-check-result.json`）：
`prepare_only=true`、`hardware_started=false`、`outside_repo_writes=[]`、
logs 恰 14 个键、`sha256.gdb_script=FF99A1E616CAF3CB…45BD5091`、
`sha256.post_gdb_script=4E3B59A132642A54…BB78519`。双脚本 SHA 与实现会话
（`DC1AAE61…`/`2439E09A…`）不同为预期行为：脚本内容嵌入 package-path 与产物路径，
本复跑参数与实现会话不同；清单要求核对的是脚本结构，结构核对如下。

会话 1 脚本（`.cache/p2-6-sd-r2/tmp/p2-6-sd-r5-review-check.gdb`，共 424 行）实测：

- `monitor WriteU32 0xE0042008 0x00001000` 恰出现 1 次，位于第 7 行（1 基），
  紧跟第 6 行 `monitor halt` 之后；全文无逗号变体（`WriteU32 0xE0042008,0x00001000`
  出现 0 次），确为空格分隔。✓
- 快照 dump 恰 2 行（第 420/421 行）：控制块
  `dump binary memory …/p2-6-sd-r5-review-check-rtt-cb-pre.bin $rtt_cb ($rtt_cb + 0xA8)`
  与 Up0 环 `…/…-rtt-up0-pre.bin $up0_pbuf ($up0_pbuf + $up0_size)`；其后第 422 行
  `SNAPSHOT_WRITTEN` printf、第 423 行 `detach`——快照 dump 与标记均在 `detach` 之前，
  且在 `P2_6_RTT_DRIVER PASS` marker（第 402 行）之后，与声明一致。✓

post 脚本（`…/p2-6-sd-r5-review-check-post.gdb`，共 17 行）实测：

- `monitor halt` 恰 1（第 6 行）、WDT 暂停行恰 1（第 7 行，紧跟 halt）；
- 签名校验 quit 41、`dump binary memory …/…-rtt-cb-post.bin`、`detach` 各 1；
- 全文 `continue`/`call `/`reset`/`loadbin`/`loadfile` 出现次数全部为 0。✓

（产物均在项目内 `.cache/p2-6-sd-r2/{logs,tmp}/` 下，属指令授权的复核临时产物。）

## 复核 6：baseline 绑定复核 — **PASS**

读取 `.cache/p2-6-sd-r5-20260830-01-implementation/offline/baseline.json`，
对其中 6 项冻结输入逐项独立复算（Python hashlib）：

| 项 | 路径 | 实测字节 | 实测 SHA-256 | baseline 记录 | 比对 |
|---|---|---|---|---|---|
| test_elf | `.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf` | 866372 B | `35BB2AB75C683FA9…5076D019` | 866372 B / 同 | 一致 |
| test_map | `.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.map` | 2423356 B | `2446B401E1C7812B…DA45D0C13` | 2423356 B / 同 | 一致 |
| image_v280 | `.cache/p2-6-sd-ota/assets/X-Track-App-GCC-p2-6a-test-v2.8.0.finalized.bin` | 600744 B | `AB38A4E75D905D30…AE569A5E5` | 600744 B / 同 | 一致 |
| image_v281 | `.cache/p2-6-sd-ota/assets/X-Track-App-GCC-p2-6a-test-v2.8.1.finalized.bin` | 600744 B | `A2D3083B25EE3281…15D58E00` | 600744 B / 同 | 一致 |
| patch_etu | `.cache/p2-6-sd-ota/assets/P2-6A-PATCH-v2.8.0-to-v2.8.1.etu` | 305 B | `2B0ACCAEABD88572…6AF37C9D2B` | 305 B / 同 | 一致 |
| full_etu | `.cache/p2-6-sd-ota/assets/P2-6A-FULL-v2.8.1.etu` | 282367 B | `84D3F38420A9521F…1EC96DD2E7` | 282367 B / 同 | 一致 |

PATCH=`2B0ACCAE…F37C9D2B` 与 FULL=`84D3F384…C96DD2E7` 确认来自
`.cache/p2-6-sd-ota/assets/` 的 P2-6A-* 系列（指令指定来源）。同时实测验证
baseline 的非冻结资产披露属实：`.cache/p2-6-progress-20260826-01/assets/` 下
`P2-6-R5-PATCH-v2.8.0-to-v2.8.1.etu`（305 B，`306129E6F7A155B5…`）与
`P2-6-R5-FULL-v2.8.1.etu`（282367 B，`95A3A30323822285…`）与冻结值**不符**，
与 baseline 披露声明的 `306129E6.../95A3A303...` 完全一致，确实不得用于 R5 步骤。
（该目录另有 `patch-roundtrip.bin`/`full-roundtrip.bin` 均为 `A2D3083B…`，属旧会话
roundtrip 产物，不在 baseline 披露范围内，不影响判定。）

## 复核 7：红线检查 — **PASS**

- **生产源码 / 冻结契约 / Tools / v1 合同矩阵**：全部为 tracked 文件，`git status`
  实测 tracked 改动仅复核 2 所列 3 个文件；`PLAN-OTA.md` 与
  `docs/ota-binary-contracts.md` 工作区与 HEAD 哈希逐一复算一致（未改）。
- **v1 合同与矩阵哈希复算**：`docs/acceptance-contracts/P2-6-v1.contract.json`
  17416 B / `BFE0F5931BEED31FE658002DBF22A814650E9A74D6C495D21D6EC710F00C9F48`、
  `docs/acceptance-contracts/P2-6-v1/P2-6-v1.evidence-matrix.json`
  14647 B / `50D7F8BA597F1BB724A86E9E069B7B03E7091A3D6A32E8D8696DC62EAE853122`，
  与裁定文档 §1 冻结值精确一致。`Tools/acceptance/**`、`Tools/provenance/**`
  零 tracked 改动。
- **.cache 既有证据根（R14-R20）**：全 `.cache` 树扫描"2026-08-30 15:00（R5 实现
  会话时段起点）之后修改的文件"共恰 7 个——实现会话的 3 个 prepare-check 产物
  （18:49，`p2-6-sd-r2/{logs,tmp}/p2-6-sd-r5-prepare-check*`）、新证据根
  `p2-6-sd-r5-20260830-01-implementation/offline/baseline.json`（18:58）、本复核的
  3 个 review-check 产物（19:10）。R14-R20 各证据根
  （`p2-6-rtt-binding-20260829-14…-23`、`p2-6-rtt-binding-20260829-18` 正式验收根、
  `p2-6-sd-r4-20260825-01-implementation`、`p2-6-sd-ota` 冻结输入等）最新文件
  mtime 全部不晚于 2026-08-30 14:02（R19/R20 时段），零触碰。新证据根
  `p2-6-sd-r5-20260830-01-implementation` 仅含声明中的 `offline/baseline.json` 一个
  文件，符合"唯一新证据根、原不存在"声明。

## 异常与披露（不构成 REJECTED 的发现）

1. **治理规则发现（环境性，非实现缺陷）**：本复核的指令文件
   `.claude/prompt-P2-6-SD-R5-independent-review.md` 因文件名含 `P2-6` 卡号前缀且
   位于 `.claude/`，触发 `test_acceptance_bundle.py` 的派单提示词位置治理规则，
   使该套件在当前工作区为 64/65（唯一失败即该测试）。根因在复核派发方的文件放置，
   不在被复核的两白名单文件（证明链见复核 3）。建议：复核派发方后续将派单/复核类
   提示词按治理规则放入 `docs/ota-prompts/`，或注意此类文件会使
   `test_acceptance_bundle.py` 在当前树复跑时变红。
2. **prepare-only 双脚本 SHA 与证据文档不同**：属参数差异（package-path/output-prefix
   嵌入脚本内容）导致的预期差异，非缺陷；本复核以结构核对（WDT 唯一性、快照在
   detach 前、post 只读性）为判据，结构全部符合。
3. **测试运行副产物**：按清单第 3 项要求直接运行 5 套测试，Python 解释器会刷新
   `tests/ota/__pycache__` 等被 git 忽略的字节码缓存（无 tracked 内容变化）；
   治理测试自身的临时探针目录按其设计用完即删，无残留。

## 总结论：**APPROVED**

R5 阶段 0（driver 两段式采集通道离线重构）通过本独立复核：七项清单全部 PASS，
未发现实质缺陷。实现会话的关键声明（修改后双哈希、白名单外零改动、离线回归全绿、
prepare-only 脚本结构、baseline 绑定、红线边界）均经本会话独立实测证实；
唯一偏差（`test_acceptance_bundle.py` 65 项中 1 项）经复现定因为复核指令文件
自身位置触发，与被复核实现无关。

**边界重申**：本 APPROVED 仅代表阶段 0 离线整改通过独立复核，满足派单裁定 §4.2
"第二个独立非实现 agent 复核"前置条件；**不构成任何硬件授权**——硬件步骤
（fresh preflight、SD 写入路径、JLinkDLL.ini 副作用等）仍需用户当轮明确授权，
R19 的 no-flash/只读结论亦不外推至 SD 写入与真实 OTA 路径。
