# -*- coding: utf-8 -*-
"""P2-6-SD-R5 派单裁定会话：PLAN-OTA-EXEC.md 字节级回写（追加裁定行 + §10 日志行）。
混合 EOL 文件，必须按字节读写；禁止 Edit 工具。"""
import sys

PATH = r"D:\github\my\E-Track\PLAN-OTA-EXEC.md"

data = open(PATH, "rb").read()
lines = data.split(b"\n")
assert lines[556].startswith(b"- P2-6-BR-20260825-RTT-CAPTURE-01"), "anchor 557 mismatch"
assert lines[557].startswith("- 实现提示词状态".encode("utf-8")), "anchor 558 mismatch"
assert lines[893].startswith("- 2026-08-30 ｜".encode("utf-8")), "anchor 894 mismatch"
assert lines[894] == b"", "tail not empty"

ruling = (
    "- P2-6-SD-R5 派单裁定 (2026-08-30): `P2-6-BR-20260830-SD-R5-01=AUTHORIZED_RESUME`，三问裁定："
    "① RTT-CAPTURE-01 解除条件以重定域形式闭合（仅限通道绑定事实，不含 driver 修复授权）："
    "R19 探针 F1 定因 telnet 通道在本 J-Link 上结构性只给 banner，绑定证明由两段式 JLinkRTTLogger+GDB "
    "只读快照逐字节完成（payload 731B 与 pending 一致、RdOff 0→731、控制块 RdOff 字外零变化），"
    "双分支 RTT_CHANNEL_BINDING_VERIFIED 并经 P2-6-v1 独立验收 PASS；"
    "② R4-01 两缺陷：uploader UNKNOWN 差一已由 R3-02 裁定授权修复(=12)并经 R4-01 上传 1/1 PASS 实证；"
    "driver 状态机误记在工作区已修复(E63F8AC6，48 项离线负例全绿，2026-08-26 独立复核重跑 OK，"
    "随 3218ff0 入库并被 P2-6-v1 Validation manifest 绑定)，但其 telnet 采集通道经 R19 定因结构性不可用，"
    "真机采集能力仍不存在；该修复发生于 §40 KEEP_BLOCKED 之后且无显式授权裁定记录，登记为治理缺口；"
    "全历史零 PRODUCT_FAIL；SD 卡曾在 R4-01 PATCH 上传(授权路径)被写入一次并读回 SHA 匹配；"
    "③ 授权新轮次 P2-6-SD-R5：fresh preflight、可选基线恢复(loadbin 仅用户明示授权)、PATCH 上传、"
    "PATCH OTA、FULL 上传、FULL OTA、异常退出、LiveMap 恢复各 0/1；"
    "test-only 白名单=tests/ota/p2_6_rtt_ota_driver.py 与其单测（采集通道移植为 R19 两段式 logger 结构，"
    "前后 SHA 记录+第二独立非实现 agent 复核后方可启硬件）；"
    "硬件前置=每 halt 会话一行 monitor WriteU32 0xE0042008 0x00001000、两段式 binding 结构、"
    "logger 生命周期披露、BCB 只读确认(非 CONFIRMED/FREE 即停)；"
    "停止条件=任一步首失败即停、峰值超 40960B/8192B、guard 损坏、required 增量非零、读回不匹配；"
    "合同=新冻结 P2-6-v2(同 task_id、version=2、parent_contract_sha256=BFE0F593... 绑定 v1，验收前冻结)；"
    "R19 no-flash 只读结论不外推至 SD 写入与真实 OTA 路径；历史配额全部不清零不重跑"
    "(R4 PATCH OTA 1/1 永不重跑)。详见 docs/ota-exec-notes/P2-6-SD-R5-dispatch-ruling-2026-08-30.md"
).encode("utf-8")

logline = (
    "- 2026-08-30 ｜ Claude（P2-6-SD-R5 非实现协调/派单裁定 agent） ｜ P2-6（三问裁定 + SD-R5 派单授权） ｜ "
    "独立裁定三问：① RTT-CAPTURE-01 解除条件以重定域形式闭合（仅限通道绑定事实，不含 driver 修复授权）；"
    "② R4-01 两缺陷现状核实（uploader 已修复实证；driver 工作区已修复但 telnet 通道结构性不可用且授权"
    "记录缺失，登记治理缺口）；全历史零 PRODUCT_FAIL、SD 曾在 R4-01 授权写入一次。"
    "裁定 P2-6-BR-20260830-SD-R5-01=AUTHORIZED_RESUME：授权新轮次 P2-6-SD-R5（每步 0/1 配额、"
    "test-only 白名单、WDT 暂停/两段式/logger 披露/BCB 只读确认硬件前置、fail-closed 停止条件、"
    "P2-6-v2 合同策略 version=2 parent=BFE0F593... 验收前冻结）；历史配额全部不清零不重跑；"
    "R19 no-flash 结论不外推至 SD 写入与真实 OTA。看板回写将使 v1 Governance manifest 当前树复验变红"
    "（R20 §6 已登记设计问题，v1 PASS 判定不受影响，复验保留于历史提交链）。"
    "本轮零硬件、零代码修改、未 commit/push。裁定文档 "
    "docs/ota-exec-notes/P2-6-SD-R5-dispatch-ruling-2026-08-30.md；看板回写用 Python 字节级操作"
).encode("utf-8")

lines.insert(557, ruling)               # 557 行(RTT-CAPTURE 裁定)后、558 行(实现提示词状态)前；LF-only
lines.insert(895, logline + b"\r")      # 原 894 行(最后日志,CRLF)后追加；CRLF 风格
out = b"\n".join(lines)
open(PATH, "wb").write(out)

# ---- 校验 ----
data2 = open(PATH, "rb").read()
text = data2.decode("utf-8")            # UTF-8 解码校验
lines2 = data2.split(b"\n")
ok_anchor1 = lines2[557] == ruling
ok_anchor2 = lines2[895] == logline + b"\r"
ok_prev557 = lines2[556].startswith(b"- P2-6-BR-20260825-RTT-CAPTURE-01")
ok_prev558 = lines2[558].startswith("- 实现提示词状态".encode("utf-8"))
ok_prev894 = lines2[894].startswith("- 2026-08-30 ｜".encode("utf-8")) and lines2[894].endswith(b"\r")
print("lines:", len(lines2), "bytes:", len(data2), "prev_bytes:", len(data))
print("insert ruling ok:", ok_anchor1, "| logline ok:", ok_anchor2)
print("context intact:", ok_prev557, ok_prev558, ok_prev894)
print("ruling CR?", lines2[557].endswith(b"\r"), "| log CR?", lines2[895].endswith(b"\r"))
sys.exit(0 if all([ok_anchor1, ok_anchor2, ok_prev557, ok_prev558, ok_prev894]) else 1)
