# P2-6-SD-R5 阶段 0 独立复核指令（交独立复核 agent 执行）

> 角色：独立复核 agent。你没有参与实现，不得接受实现会话的任何口头结论；
> 只依据本清单、仓库实况与证据文档自行执行并下结论。零硬件、零 git 写操作、
> 不改任何文件（唯一例外：落盘你自己的复核报告）。

## 复核对象

R5 阶段 0（driver 两段式采集通道离线重构）的实现声明，见
`docs/ota-exec-notes/P2-6-SD-R5-phase0-offline-evidence-2026-08-30.md`。
授权依据：`docs/ota-exec-notes/P2-6-SD-R5-dispatch-ruling-2026-08-30.md`
（P2-6-BR-20260830-SD-R5-01，§4.2 白名单 = 仅
`tests/ota/p2_6_rtt_ota_driver.py` 与 `tests/ota/test_p2_6_rtt_ota_driver.py`）。

## 机械复核清单（逐项执行，逐项记录实测值）

1. **哈希复算**：用 certutil 或 Python 复算两白名单文件的字节数与 SHA-256，
   与证据文档 §1 的"修改后"值逐项比对：
   - driver 应为 70942 B / `1B092AF294850AC353D48116D9205A5C1F9E9EF7476D51425891338735A64C56`
   - 单测应为 53997 B / `411E01A7C866C74E440B43F97695602B7D2BF0DC6037A1EE2EEBBCFFE51CD5FB`
2. **diff 范围审计**：`git status --short` + `git diff --stat` 确认 tracked 改动
   仅限两白名单文件与 `PLAN-OTA-EXEC.md`（看板登记性追加，允许）；确认
   `tests/ota/p2_6_rtt_sd_uploader.py`、`p2_6_rtt_sd_preflight.py`、
   `p2_6_rtt_transport_qualifier.py` 及其全部单测零改动。
3. **fixture 重跑**（全部独立执行，不得引用实现会话的运行结果）：
   ```
   cd D:\github\my\E-Track\tests\ota
   python test_p2_6_rtt_ota_driver.py      # 预期 38 项 OK
   python test_p2_6_rtt_sd_preflight.py    # 3 项 OK
   python test_p2_6_rtt_sd_uploader.py     # 7 项 OK
   python test_p2_6_rtt_transport_qualifier.py  # 4 项 OK
   python test_acceptance_bundle.py        # 65 项 OK
   ```
4. **§40.6 五项修复门槛独立核验**（读代码本身，不信文档自述）：
   - socket connected ≠ payload ready（probe_rtt_telnet 只做可达性；
     rtt_payload_ready 由 derive+capture 组合触发）
   - banner-only/截断/缺失/socket 错误/超时/channel 未证实全部 fail-closed
     （classify_transport_session 两级 + derive/capture/postcheck 失败路径）
   - 有界采集 + 恰一条匹配 kind 完整记录（derive 的 records==1/matching==1
     与 logger settle 静默期；重复失败）
   - GDB 非零优先于 payload 判定；server 强制收尾/端口残留 fail-closed
   - 负例 fixture 实际存在且有效（在单测源码中逐一找到对应用例名）
5. **prepare-only 独立复跑**（MSYS 路径屏蔽）：
   ```
   MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' python tests/ota/p2_6_rtt_ota_driver.py ^
     --prepare-only --kind PATCH --package-path "/P2-6-SD-R5-REVIEW-CHECK/review.etu" ^
     --output-prefix p2-6-sd-r5-review-check
   ```
   打开生成的 `.gdb` 与 `-post.gdb` 实测核对：monitor halt 后恰一行
   `monitor WriteU32 0xE0042008 0x00001000`（空格分隔）；快照 dump 在
   `detach` 之前；post 脚本全文零 `continue`/`call `/`reset`/`loadbin`。
6. **baseline 绑定复核**：读
   `.cache/p2-6-sd-r5-20260830-01-implementation/offline/baseline.json`，
   独立复算其中 6 项冻结输入哈希（尤其 PATCH=`2B0ACCAE…`、FULL=`84D3F384…`
   来自 `.cache/p2-6-sd-ota/assets/` 的 P2-6A-* 系列；注意
   `p2-6-progress-20260826-01` 下的同名资产哈希不符，不得使用）。
7. **红线检查**：确认实现未触碰生产源码、冻结契约（PLAN-OTA.md、
   docs/ota-binary-contracts.md）、Tools/acceptance、Tools/provenance、
   `.cache` 既有证据根（R14-R20）、v1 合同与矩阵。

## 输出

落盘 `docs/ota-exec-notes/P2-6-SD-R5-independent-review-2026-08-30.md`：
逐项实测值 + 结论（`APPROVED` 或 `REJECTED` + 缺陷清单）。APPROVED 仅代表
阶段 0 离线整改通过复核，不构成硬件授权——硬件步骤仍需用户当轮明确授权。

## 边界

- 零硬件：不得启动 J-Link/GDB server/RTT logger/OTA，不得写 SD/Flash/目标内存。
- 零 git 写操作：不 commit/push/merge/stash。
- 除你的复核报告与 prepare-only 的项目内临时产物外，不写任何文件。
- 发现任何一项不符即 REJECTED 并停在该项，不修补、不继续。
