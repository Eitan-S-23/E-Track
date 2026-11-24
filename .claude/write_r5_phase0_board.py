# -*- coding: utf-8 -*-
"""R5 阶段 0 完成后看板回写：P2-6 卡追加实现行 + §10 日志行（字节级）。"""
import sys

PATH = r"D:\github\my\E-Track\PLAN-OTA-EXEC.md"

data = open(PATH, "rb").read()
lines = data.split(b"\n")
ruling_idx = None
for i, line in enumerate(lines):
    if line.startswith("- P2-6-SD-R5 派单裁定".encode("utf-8")):
        ruling_idx = i
        break
assert ruling_idx is not None, "R5 ruling line not found"
assert lines[ruling_idx + 1].startswith("- 实现提示词状态".encode("utf-8")), "anchor after ruling mismatch"
last_log_idx = None
for i, line in enumerate(lines):
    if line.startswith("- 2026-08-30 ｜".encode("utf-8")):
        last_log_idx = i
assert last_log_idx is not None and lines[last_log_idx].endswith(b"\r"), "last log line anchor mismatch"

phase0 = (
    "- P2-6-SD-R5 阶段 0 离线实现完成 (2026-08-30): 用户在会话中明确授权原派单裁定 agent 转任 R5 实现 agent"
    "（角色转换已登记，独立复核与独立验收两道制衡不变）。按 P2-6-BR-20260830-SD-R5-01 白名单完成 driver 采集通道"
    "两段式重构：删除 RttCapture telnet 采集线程（该通道结构性只给 banner），telnet 降级为 transport 可达性探针"
    "（banner 记录、非 SEGGER banner fail-closed，rtt_connected 语义保留供 qualifier）；会话 1 OTA 脚本尾部"
    "（halted 态、detach 前）新增 RTT 控制块+Up0 环快照 dump；attach 后插入恰一行 WDT 暂停"
    "（monitor WriteU32 0xE0042008 0x00001000，空格分隔）；新增 derive_rtt_pending（R19 precheck 语义："
    "签名/缓冲计数/pBuffer SRAM 范围/尺寸 1024/Flags/偏移全 fail-closed，pending 须恰一条匹配记录）、"
    "run_rtt_logger_capture（R19 capture 语义：独立 JLinkRTTLogger probe 连接、payload 与 pending 逐字节一致、"
    "settle 无额外字节、Stop-Process 残留清理 fail-closed）、post_snapshot_command_file + verify_rtt_postcheck"
    "（R19 postcheck 语义：WrOff 不变、RdOff 恰好消费库存、控制块 4B RdOff 字外零变化）与 "
    "run_two_phase_ota_session 编排；classify 拆分 RTT_PAYLOAD_FAIL/RTT_POSTCHECK_FAIL 两级且 GDB_FAIL 优先；"
    "hardware_run 新产物全纳入唯一性保护与 result 绑定并加 rtt_channel_binding_verified 门禁。"
    "修改仅限白名单两文件（driver 51578B/E63F8AC6… → 70942B/1B092AF2…；单测 44202B/3DB14270… → "
    "53997B/411E01A7…；uploader/preflight/qualifier 及其单测零改动）。离线回归全绿：driver 单测 38 项 OK"
    "（含两段式 16 项新负例：空库存/重复/异 kind/截断/capture 超时/额外字节/不一致/postcheck 三类越界/post 会话"
    "失败/GDB 非零/binding 不自证/derive 8 结构负例/环回绕库存/logger mock 负例/脚本静态断言）、preflight 3 + "
    "uploader 7 + qualifier 4 + acceptance bundle 65 全 OK；py_compile 与 --self-test 通过；prepare-only 端到端"
    "实测生成脚本（快照段第 420-422 行 detach 前、WDT 行唯一、post 脚本零 continue/call/reset）。"
    "§40.6 五项修复门槛逐项对照通过（见证据文档 §5）。下一步：第二个独立非实现 agent 复核（复算 hash、"
    "diff 仅限白名单、重跑 fixture）通过后方可按用户当轮授权启动硬件步骤；本阶段零硬件。证据："
    "docs/ota-exec-notes/P2-6-SD-R5-phase0-offline-evidence-2026-08-30.md"
).encode("utf-8")

logline = (
    "- 2026-08-30 ｜ Claude（P2-6-SD-R5 实现 agent，原派单裁定会话经用户当轮授权转任） ｜ "
    "P2-6（SD-R5 阶段 0：driver 两段式采集通道离线重构） ｜ 按派单裁定白名单完成 "
    "tests/ota/p2_6_rtt_ota_driver.py 与其单测的重构：telnet 采集线程删除、探针降级、会话 1 快照段+WDT 暂停行、"
    "derive/logger capture/postcheck 三阶段与编排、classify 两级拆分、hardware_run 门禁接线；"
    "离线回归 38+3+7+4+65 全绿，prepare-only 实测生成脚本合规，§40.6 五项门槛逐项对照通过；"
    "白名单外文件零改动、零硬件、未 commit/push。待第二个独立非实现 agent 复核后方可启动硬件。"
    "证据文档 docs/ota-exec-notes/P2-6-SD-R5-phase0-offline-evidence-2026-08-30.md；看板回写用 Python 字节级操作"
).encode("utf-8")

lines.insert(ruling_idx + 1, phase0)                 # 裁定行后、实现提示词状态行前；LF-only
lines.insert(last_log_idx + 2, logline + b"\r")      # 最后日志行后；CRLF
out = b"\n".join(lines)
open(PATH, "wb").write(out)

data2 = open(PATH, "rb").read()
lines2 = data2.split(b"\n")
ok1 = lines2[ruling_idx + 1] == phase0
ok2 = lines2[ruling_idx + 2].startswith("- 实现提示词状态".encode("utf-8"))
ok3 = any(l == logline + b"\r" for l in lines2)
print("lines:", len(lines2), "insert phase0:", ok1, "| prompt-state intact:", ok2, "| logline:", ok3)
sys.exit(0 if all([ok1, ok2, ok3]) else 1)
