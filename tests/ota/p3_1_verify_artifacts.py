#!/usr/bin/env python3
"""P3-1 验收：独立复算构建产物 SHA-256，与实现方申报值逐一比对。

实现方在 `docs/ota-exec-notes/P3-1-build-evidence.md` §4 申报了 9 个产物的
时间戳/大小/SHA-256。验收不采信申报值，本脚本把申报值硬编码为"待验证输入"，
从磁盘重新读取字节重算，任一不符即失败。

退出码：0=9/9 全部一致；1=存在不一致或缺失。
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
BUILD = "MDK-ARM_F435/cmake-generated/build-gcc-release"

# (相对路径, 申报大小, 申报 SHA-256) —— 均摘自 P3-1-build-evidence.md §4
DECLARED = [
    (f"{BUILD}/app-gcc/X-Track-App-GCC.elf", 867952,
     "4a5f673ae775c7c72a481a44f32350a13635b168de5a954c5985e4ca74773a87"),
    (f"{BUILD}/app-gcc/X-Track-App-GCC.hex", 1694382,
     "cb6de4c884a96577cfff9dd3ee811652e01d46394e8e5ecd0a9e7191371fcef1"),
    (f"{BUILD}/app-gcc/X-Track-App-GCC.bin", 602864,
     "4c44622a7716197278a85a569ad2247cf1e0bc1816edd5c650b40b354f33e30d"),
    (f"{BUILD}/app-gcc/X-Track-App-GCC.map", 2433909,
     "057fce1c10997e8695bea43afa66fba8b738ec4adbf8010794f78bc7a50241d9"),
    (f"{BUILD}/boot/X-Track-Boot.elf", 36860,
     "d21713ca2c1efeac949f8ec0ffddacac439fed6bf26f9c65641bee24464fdabc"),
    (f"{BUILD}/boot/X-Track-Boot.hex", 41485,
     "ff3badef69be6d97fd66815b8df90efd962a708b559c8951d4b56380f8001f71"),
    (f"{BUILD}/boot/X-Track-Boot.bin", 14724,
     "5842ff3e19ba9e1eaaea10f27e825c7b6efc278b200531014b0dba61264f6594"),
    (f"{BUILD}/boot/X-Track-Boot.map", 100450,
     "14e7a8addd37dfe71744c11ab0db60d5c535fbe725fe3e950f82354f34a4fc93"),
    ("Simulator/Output/Debug/x64/LVGL.Simulator.exe", 5864960,
     "9952365787183701b753c3317d0b33a2f6c059d39b567dd2c020dd2b8af7300f"),
]


def main() -> int:
    match = mismatch = missing = 0
    print("对 P3-1-build-evidence.md §4 申报的 9 个产物独立复算：\n")
    for rel, exp_size, exp_hash in DECLARED:
        path = ROOT / rel
        if not path.is_file():
            print(f"[MISSING] {rel}")
            missing += 1
            continue
        data = path.read_bytes()
        act_size = len(data)
        act_hash = hashlib.sha256(data).hexdigest()
        ok = act_size == exp_size and act_hash == exp_hash.lower()
        if ok:
            match += 1
            print(f"[MATCH   ] {rel}")
            print(f"            size={act_size}  sha256={act_hash}")
        else:
            mismatch += 1
            print(f"[MISMATCH] {rel}")
            print(f"            申报 size={exp_size} sha256={exp_hash}")
            print(f"            实测 size={act_size} sha256={act_hash}")

    total = len(DECLARED)
    print(f"\n=== 一致 {match} / 不一致 {mismatch} / 缺失 {missing}（共 {total}）===")
    ok = mismatch == 0 and missing == 0
    print(f"P3_1_ARTIFACTS={'PASS' if ok else 'FAIL'} match={match} "
          f"mismatch={mismatch} missing={missing} total={total}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
