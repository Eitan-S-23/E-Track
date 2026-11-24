# -*- coding: utf-8 -*-
# P3-3 第五批整改交付看板回写（字节级，保既有行尾）。
# 模式沿用 write_p33_batch4_board.py：rb 读 → 三步唯一锚点替换/插入/追加 → wb 写。
# 1) L622 状态行「更新：」字段 → 第五批交付文本（卡保持进行中）
# 2) L634 第四批复核记录后插入第五批交付记录（LF，与 L632-634 一致）
# 3) 文件末尾追加 §10 会话日志一行（LF，与 L1015-1017 一致）
import io

PATH = r"D:\github\my\E-Track\PLAN-OTA-EXEC.md"

with io.open(PATH, "rb") as f:
    data = f.read()

# ---- 步骤 1：状态行「更新」字段替换 ----
old_update = (
    "更新: 2026-09-08(RC3 第四批整改独立集中复核：原编译/Windows 能力等源码"
    "子项已修，测试 oracle、取消/迟到操作、ACK 错误传播、恢复闭锁与流清理"
    "仍未闭合，逐项见 research §6.12；analyze/test/APK/EXE/真机及正式验收 "
    "NOT_RUN，先批量整改与可信自测)"
).encode("utf-8")
new_update = (
    "更新: 2026-09-08(RC3 第五批整改交付：按 §6.12.2 逐项完成测试可信度/"
    "fake MCU 真值/取消交错/末块 ACK/慢写反例/恢复闭锁/HTTP 闭锁/流取消的"
    "代码修改并逐项落盘复核，§6.12.3 反例按结论不改，见 research §6.13；"
    "analyze/test/APK/EXE/真机及正式验收 NOT_RUN，已修不等于运行验证通过)"
).encode("utf-8")
assert data.count(old_update) == 1, "状态行更新字段锚点不唯一或缺失"
data = data.replace(old_update, new_update)

# ---- 步骤 2：L634 后插入第五批交付记录 ----
anchor_record = (
    "- RC3 第四批整改独立集中复核(非正式轮次): Codex(非实现会话)/2026-09-08；"
    "确认 §6.11 新交付落盘"
).encode("utf-8")
new_record = (
    "- RC3 第五批整改交付(实现会话): Claude(P3-3-IMPL-20260907)/2026-09-08；"
    "按 §6.12.2 逐项处置表完成 RC3-02⑤/03⑤/04⑤/05⑤/06⑤/07⑤/08⑤12⑤/10⑤/11⑤ "
    "的 lib 修复与测试重写/补充(含小 MTU 分片在途取消、块尾锁存错误消费、慢写 "
    "WRITE_TIMEOUT 反例、身份漂移作废旧清单旧包、INVALID_PARAMETER 下载闭锁、"
    "早退 drain 主动取消与首块停滞时间界)，逐项记录见 "
    "docs/ota-exec-notes/P3-3-research-flutter-ota.md §6.13；§6.12.3 反例纠正"
    "按复核结论维持不改。交付前对四个测试文件与 lib 锚点逐项落盘复核全部存在；"
    "但 Flutter analyze/test、Actions APK/EXE、真机全部 NOT_RUN(无本机 SDK、"
    "未获推送授权)，已修不等于运行验证通过。未 commit/push/dispatch/真机；"
    "保持进行中，不填 PASS 矩阵，正式验收待非实现独立会话。\n"
).encode("utf-8")
# 锚定完整 L634 行 + 其 LF 行尾，随后插入新行（LF）
record_line_prefix = None
pos = data.find(anchor_record)
assert pos != -1, "第四批复核记录锚点缺失"
line_end = data.find(b"\n", pos)
assert line_end != -1, "第四批复核记录行尾缺失"
record_line = data[pos:line_end]
assert not record_line.endswith(b"\r"), "第四批复核记录行意外为 CRLF"
old_block = record_line + b"\n"
new_block = record_line + b"\n" + new_record
data = data.replace(old_block, new_block, 1)

# ---- 步骤 3：末尾追加 §10 日志一行 ----
log_line = (
    "- 2026-09-08 ｜ Claude(P3-3 实现 agent, P3-3-IMPL-20260907) ｜ "
    "P3-3(保持进行中，RC3 第五批整改交付) ｜ 按 §6.12.2 完成 RC3-02⑤~11⑤ "
    "测试侧与 lib 补接线并逐项落盘复核(research §6.13)；analyze/test/APK/EXE/"
    "真机 NOT_RUN(无 SDK/未获授权)，未 commit/push/dispatch，不填 PASS 矩阵，"
    "正式验收待非实现会话。\n"
).encode("utf-8")
assert data.endswith(b"\n"), "文件不以换行结尾，追加前需人工核对"
data = data + log_line

with io.open(PATH, "wb") as f:
    f.write(data)

print("board written, new size", len(data))
