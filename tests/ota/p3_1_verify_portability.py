#!/usr/bin/env python3
"""P3-1 验收：反斜杠 `#include` 可移植性扫描（自带阳性对照）。

`AGENTS.md` 「GCC / Linux CI 源码可移植防坑」把反斜杠 include 列为硬失败
红线：Linux GCC 不把 `\\` 当路径分隔符，本机 Windows 构建绿不能证明 CI 绿。

"0 命中"本身可能来自正则失效，因此本脚本强制要求先在 `.old` 存档上命中
已知阳性样本；阳性对照为空时直接判失败，杜绝把扫描失效误读为通过。

退出码：0=阳性对照命中且参与编译的手写源 0 命中；1=其余一切情况。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
PATTERN = re.compile(r'#\s*include\s*["<][^">]*\\')
SCAN_DIRS = ["Libraries", "USER", "MDK-ARM_F435/Platform"]
EXTS = {".c", ".cpp", ".h", ".hpp", ".cc", ".old"}
# P3-1 新增的三对源/头，必须单独确认零命中
P3_1_NEW_SOURCES = [
    "Libraries/OTA/ota_ble_ring.c", "Libraries/OTA/ota_ble_ring.h",
    "Libraries/OTA/ota_ble_frame.c", "Libraries/OTA/ota_ble_frame.h",
    "Libraries/OTA/ota_ble_session.c", "Libraries/OTA/ota_ble_session.h",
]


def main() -> int:
    hits: list[tuple[str, int, str]] = []
    scanned = 0
    for name in SCAN_DIRS:
        for path in sorted((ROOT / name).rglob("*")):
            if not path.is_file() or path.suffix.lower() not in EXTS:
                continue
            if any(p.startswith("build") or p == "vendor" for p in path.parts):
                continue
            scanned += 1
            text = path.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                if PATTERN.search(line):
                    hits.append((path.relative_to(ROOT).as_posix(), lineno, line.strip()))

    archived = [h for h in hits if h[0].endswith(".old")]
    live = [h for h in hits if not h[0].endswith(".old")]
    new_src_hits = [h for h in live if h[0] in P3_1_NEW_SOURCES]

    print(f"扫描目录 = {SCAN_DIRS}")
    print(f"扫描文件数 = {scanned}")
    print(f"\n[阳性对照] .old 存档命中 {len(archived)} 处")
    for item in archived[:5]:
        print(f"  {item[0]}:{item[1]}  {item[2]}")
    if not archived:
        print("  !! 阳性对照为空：正则可能失效，本次扫描结论不可采信")

    print(f"\n[正式] 参与编译的手写源命中 {len(live)} 处")
    for item in live[:20]:
        print(f"  {item[0]}:{item[1]}  {item[2]}")
    if not live:
        print("  （无命中 = CI 可移植性红线通过）")

    print(f"\n[P3-1 新源] {len(P3_1_NEW_SOURCES)} 个文件命中 {len(new_src_hits)} 处")

    ok = bool(archived) and not live
    print(f"\nP3_1_PORTABILITY={'PASS' if ok else 'FAIL'} scanned={scanned} "
          f"control_hits={len(archived)} live_hits={len(live)} new_src_hits={len(new_src_hits)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
