#!/usr/bin/env python3
"""P3-1 验收：冻结契约 §5 与实现头文件常量的机器比对。

`AGENTS.md` OTA 执行规约 §2 规定 `docs/ota-binary-contracts.md` 为冻结契约、
只读。本脚本从契约 markdown 表格解析权威常量，与
`Libraries/OTA/ota_ble_frame.h` 的 `#define` 逐项核对，任何漂移即失败。
人工"逐项比对"不可复现，故一律以本脚本结论为准。

退出码：0=零漂移；1=存在漂移或解析失效。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/ota-binary-contracts.md"
HEADER = ROOT / "Libraries/OTA/ota_ble_frame.h"

# 契约小节标题 -> 该表在契约中的语义
SECTION_CMD = "### 5.2 命令表"
SECTION_INFO = "#### 5.2.1 INFO payload"
SECTION_BEGIN = "### 5.3 BEGIN payload"
SECTION_STATUS = "### 5.7 状态码表"


def read_defines(path: Path) -> dict[str, int]:
    """解析头文件 `#define NAME 0xNNu / Nu` 为整数表。"""
    out: dict[str, int] = {}
    pattern = re.compile(r"^#define\s+(OTA_BLE_[A-Z0-9_]+)\s+(0[xX][0-9A-Fa-f]+|\d+)u?\s*$")
    for line in path.read_text(encoding="utf-8").splitlines():
        m = pattern.match(line.strip())
        if m:
            out[m.group(1)] = int(m.group(2), 0)
    return out


def slice_section(text: str, start: str) -> str:
    """截取从 start 标题到下一个同级或更高级标题之间的正文。"""
    idx = text.find(start)
    if idx < 0:
        raise SystemExit(f"契约缺少小节: {start}")
    body = text[idx + len(start):]
    nxt = re.search(r"^#{2,4} ", body, re.MULTILINE)
    return body[: nxt.start()] if nxt else body


def parse_hex_name_table(section: str) -> dict[int, str]:
    """解析 `| 0xNN | NAME | ...` 形式的表格，返回 {值: 名称}。"""
    out: dict[int, str] = {}
    for line in section.splitlines():
        m = re.match(r"^\|\s*(0[xX][0-9A-Fa-f]{2})\s*\|\s*([A-Za-z_][A-Za-z0-9_]*)\s*\|", line)
        if m:
            out[int(m.group(1), 0)] = m.group(2)
    return out


def parse_offset_table(section: str) -> list[tuple[int, int, str]]:
    """解析 `| off | size | 字段 | 说明 |` 形式的表格。"""
    rows: list[tuple[int, int, str]] = []
    for line in section.splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([A-Za-z_][A-Za-z0-9_]*)\s*\|", line)
        if m:
            rows.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    return rows


def parse_ack_map(section: str) -> dict[str, int]:
    """从 §5.2 命令表的"应答"列解析下行命令 -> ACK cmd 值。

    契约把 4 个 ACK 写成 `0x81..0x84` 范围行，单值解析取不到，必须由
    `| 0x01 | BEGIN | 下 | §5.3 | 0x81 ACK(含 session) |` 这类行的末列还原。
    """
    out: dict[str, int] = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        if not re.fullmatch(r"0[xX][0-9A-Fa-f]{2}", cells[0]):
            continue
        name = cells[1]
        m = re.search(r"(0[xX][0-9A-Fa-f]{2})\s*ACK", cells[4])
        if m:
            out[name] = int(m.group(1), 0)
    return out


def main() -> int:
    text = CONTRACT.read_text(encoding="utf-8")
    defines = read_defines(HEADER)
    checks: list[tuple[str, object, object]] = []  # (说明, 契约值, 实现值)

    # --- §5.2 命令表：cmd 值 <-> OTA_BLE_CMD_* ---
    cmd_section = slice_section(text, SECTION_CMD)
    cmd_table = parse_hex_name_table(cmd_section)
    if len(cmd_table) < 6:
        raise SystemExit(f"命令表解析失效：仅解析到 {len(cmd_table)} 行（应 >=6）")
    for value, name in sorted(cmd_table.items()):
        macro = f"OTA_BLE_CMD_{name}"
        checks.append((f"§5.2 cmd {name}", value, defines.get(macro, "<缺失>")))

    # --- §5.2 应答列：ACK cmd 值 <-> OTA_BLE_CMD_ACK_* ---
    ack_map = parse_ack_map(cmd_section)
    if len(ack_map) < 4:
        raise SystemExit(f"应答列解析失效：仅解析到 {len(ack_map)} 项（应 >=4）")
    for name, value in sorted(ack_map.items(), key=lambda kv: kv[1]):
        macro = f"OTA_BLE_CMD_ACK_{name}"
        checks.append((f"§5.2 {name} 应答 ACK", value, defines.get(macro, "<缺失>")))
    # 实现不得多出契约未定义的命令码
    impl_cmd = {v for k, v in defines.items() if k.startswith("OTA_BLE_CMD_")}
    contract_cmd = set(cmd_table) | set(ack_map.values())
    checks.append(("§5.2 命令码集合完全一致", sorted(contract_cmd), sorted(impl_cmd)))

    # --- §5.7 状态码表：status 值 <-> OTA_BLE_STATUS_* ---
    status_section = slice_section(text, SECTION_STATUS)
    status_table = parse_hex_name_table(status_section)
    if len(status_table) < 15:
        raise SystemExit(f"状态码表解析失效：仅解析到 {len(status_table)} 行（应 >=15）")
    for value, name in sorted(status_table.items()):
        macro = f"OTA_BLE_STATUS_{name}"
        checks.append((f"§5.7 status {name}", value, defines.get(macro, "<缺失>")))
    # 状态码表必须是唯一来源：实现不得多出契约未定义的状态码
    impl_status = {v for k, v in defines.items() if k.startswith("OTA_BLE_STATUS_")}
    checks.append(("§5.7 状态码集合完全一致", sorted(status_table), sorted(impl_status)))

    # --- §5.2.1 INFO payload 长度与恒定字段 ---
    info_rows = parse_offset_table(slice_section(text, SECTION_INFO))
    if not info_rows:
        raise SystemExit("INFO payload 表解析失效")
    info_len = max(off + size for off, size, _ in info_rows)
    checks.append(("§5.2.1 INFO payload 长度", info_len, defines.get("OTA_BLE_LEN_INFO", "<缺失>")))
    checks.append(("§5.2.1 proto_ver 恒 1", 1, defines.get("OTA_BLE_INFO_PROTO_VER", "<缺失>")))
    checks.append(("§5.2.1 max_window_segs 恒 32", 32,
                   defines.get("OTA_BLE_INFO_MAX_WINDOW_SEGS", "<缺失>")))

    # --- §5.3 BEGIN payload 长度 ---
    begin_rows = parse_offset_table(slice_section(text, SECTION_BEGIN))
    if not begin_rows:
        raise SystemExit("BEGIN payload 表解析失效")
    begin_len = max(off + size for off, size, _ in begin_rows)
    checks.append(("§5.3 BEGIN payload 长度", begin_len,
                   defines.get("OTA_BLE_LEN_BEGIN", "<缺失>")))

    # --- §5.1 帧布局：sync/帧头/CRC 宽度 ---
    checks.append(("§5.1 sync0", 0xA5, defines.get("OTA_BLE_SYNC0", "<缺失>")))
    checks.append(("§5.1 sync1", 0x5A, defines.get("OTA_BLE_SYNC1", "<缺失>")))
    # A5 5A(2) + cmd(1) + session(1) + seq(2) + len(2) = 8
    checks.append(("§5.1 帧头 8B", 8, defines.get("OTA_BLE_HEADER_SIZE", "<缺失>")))
    checks.append(("§5.1 crc16 2B", 2, defines.get("OTA_BLE_CRC_SIZE", "<缺失>")))

    # --- §5.4 / §5.5 DATA 分段 ---
    checks.append(("§5.4 DATA 最小 payload = u32 off", 4,
                   defines.get("OTA_BLE_LEN_DATA_MIN", "<缺失>")))
    # §5.5 段净荷恒 128B，故 DATA 最大 payload = 4 + 128 = 132
    checks.append(("§5.5 DATA 最大 payload = 4 + 128", 132,
                   defines.get("OTA_BLE_MAX_PAYLOAD", "<缺失>")))

    # --- §5.6 ACK 长度 ---
    checks.append(("§5.6 ACK_BEGIN 10B", 10, defines.get("OTA_BLE_LEN_ACK_BEGIN", "<缺失>")))
    checks.append(("§5.6 ACK 其余 9B", 9, defines.get("OTA_BLE_LEN_ACK_OTHER", "<缺失>")))

    # --- §5.2 END payload = package_sha256(32B) ---
    checks.append(("§5.2 END payload 32B", 32, defines.get("OTA_BLE_LEN_END", "<缺失>")))
    checks.append(("§5.2 GET_INFO payload 0B", 0, defines.get("OTA_BLE_LEN_GET_INFO", "<缺失>")))
    checks.append(("§5.2 ABORT payload 0B", 0, defines.get("OTA_BLE_LEN_ABORT", "<缺失>")))

    drift = 0
    print(f"契约: {CONTRACT.relative_to(ROOT).as_posix()}")
    print(f"实现: {HEADER.relative_to(ROOT).as_posix()}")
    print(f"解析到 #define {len(defines)} 项；命令表 {len(cmd_table)} 行；"
          f"状态码表 {len(status_table)} 行\n")
    for desc, expected, actual in checks:
        ok = expected == actual
        drift += 0 if ok else 1
        mark = "OK  " if ok else "DRIFT"
        print(f"[{mark}] {desc}: 契约={expected} 实现={actual}")

    print(f"\n=== 契约漂移项 = {drift} / 核对项 = {len(checks)} ===")
    print(f"P3_1_CONTRACT_ALIGNMENT={'PASS' if drift == 0 else 'FAIL'} drift={drift} checks={len(checks)}")
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
