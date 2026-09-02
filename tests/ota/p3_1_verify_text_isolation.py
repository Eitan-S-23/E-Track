#!/usr/bin/env python3
"""P3-1 验收：文本协议与 OTA 二进制帧的隔离性。

冻结契约 §5.1 要求：UART 收到 `A5 5A` 进入二进制 OTA 处理器，其余字节走现有
TinyBTPlus 文本协议；OTA 会话期间关闭文本回显、关闭 200ms `X-Trace` 周期上行、
暂停调试透传，上行只允许 ACK/事件帧。

单看测试或单看源码都不足以定案：测试证明行为，源码证明接线。本脚本两者都做，
且行为侧自己重跑 session 测试解析输出，不读可能过期的历史日志。

退出码：0=行为与接线全部满足；1=任一项不满足。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
SESSION_TEST = ROOT / "tests/ota/test_ota_ble_session.py"
HAL_BT = ROOT / "USER/HAL/HAL_Bluetooth.cpp"
HAL_CONFIG = ROOT / "USER/HAL/HAL_Config.h"

# 必须在 session 测试中出现且为 PASS 的隔离性用例（子串匹配）
REQUIRED_CASES = [
    "idle-phase text bytes reach the text sink",
    "active-phase text bytes are dropped and never reach the sink",
    "text passthrough resumes after teardown",
]


def main() -> int:
    failures: list[str] = []

    # --- 行为侧：重跑 session 测试，解析隔离性用例 ---
    proc = subprocess.run([sys.executable, str(SESSION_TEST)],
                          cwd=ROOT, capture_output=True, text=True)
    out = proc.stdout
    print(f"[行为] 重跑 {SESSION_TEST.relative_to(ROOT).as_posix()}  exit={proc.returncode}")
    if proc.returncode != 0:
        failures.append(f"session 测试整体失败 exit={proc.returncode}")

    for case in REQUIRED_CASES:
        line = next((ln for ln in out.splitlines() if case in ln), None)
        if line is None:
            print(f"       [缺失] {case}")
            failures.append(f"隔离性用例缺失: {case}")
        elif "PASS" not in line:
            print(f"       [失败] {line.strip()}")
            failures.append(f"隔离性用例未通过: {case}")
        else:
            print(f"       [PASS] {case}")

    # --- 接线侧 1：生产构型关闭调试透传 ---
    cfg = HAL_CONFIG.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^#define\s+CONFIG_BT_USE_TRANSPARENT\s+(\d+)", cfg, re.MULTILINE)
    transparent = int(m.group(1)) if m else None
    print(f"\n[接线] CONFIG_BT_USE_TRANSPARENT = {transparent}（生产构型须为 0）")
    if transparent != 0:
        failures.append(f"CONFIG_BT_USE_TRANSPARENT 非 0: {transparent}")

    bt = HAL_BT.read_text(encoding="utf-8", errors="replace")
    bt_lines = bt.splitlines()

    # --- 接线侧 2：200ms X-Trace 周期上行受 OTA 活跃期门控 ---
    trace_idx = [i for i, ln in enumerate(bt_lines) if 'printf("X-Trace' in ln]
    print(f"[接线] X-Trace 周期上行发送点 {len(trace_idx)} 处")
    if not trace_idx:
        failures.append("找不到 X-Trace 周期上行发送点，接线断言无法成立")
    for i in trace_idx:
        window = "\n".join(bt_lines[max(0, i - 6):i])
        guarded = re.search(r"if\s*\(\s*!\s*ota_ble_session_active\s*\(", window) is not None
        print(f"       行 {i + 1}: 受 !ota_ble_session_active 门控 = {guarded}")
        if not guarded:
            failures.append(f"HAL_Bluetooth.cpp:{i + 1} 的 X-Trace 上行未受 OTA 活跃期门控")

    # --- 接线侧 3：OTA 活跃期文本 sink 置空（文本回显关闭）---
    sink_guard = re.search(
        r"ota_ble_session_active\s*\([^)]*\)\s*\?\s*NULL\s*:\s*\w*text_sink", bt)
    print(f"[接线] 活跃期文本 sink 置 NULL: {sink_guard is not None}")
    if sink_guard is None:
        failures.append("未找到活跃期把文本 sink 置 NULL 的接线")
    else:
        print(f"       {sink_guard.group(0)}")

    print(f"\n=== 失败项 {len(failures)} ===")
    for f in failures:
        print(f"  FAIL: {f}")
    ok = not failures
    print(f"P3_1_TEXT_ISOLATION={'PASS' if ok else 'FAIL'} "
          f"cases={len(REQUIRED_CASES)} transparent={transparent} "
          f"trace_points={len(trace_idx)} sink_guard={sink_guard is not None}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
