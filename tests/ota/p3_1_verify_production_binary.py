#!/usr/bin/env python3
"""P3-1 验收：生产 GCC 二进制的红线静态实证。

只看源码和文档不足以证明"新代码真的进了生产固件、测试脚手架真的没进"。
本脚本一律从生产 ELF 的符号表与链接 map 取证：

1. 新增 BLE 层公共 API 逐个存在于生产 ELF（排除孤儿源/被优化掉）。
2. 测试专有符号在生产 ELF 中一个都不存在（生产构型纯净）。
3. `ota_ble_frame.c` 不用 memcpy 解析 wire（避免结构体对齐/字节序依赖）。
4. P3-1 新源零动态分配（嵌入式无堆约束）。
5. map 实证 `.ota_overlay` 尺寸、BLE 会话控制块主 RAM 占用、A5 栈封顶断言。

退出码：0=全部红线通过；1=任一红线失败。
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "MDK-ARM_F435/cmake-generated/build-gcc-release"
APP_ELF = BUILD / "app-gcc/X-Track-App-GCC.elf"
APP_MAP = BUILD / "app-gcc/X-Track-App-GCC.map"

NM_CANDIDATES = [
    "arm-none-eabi-nm",
    r"D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming/bin/arm-none-eabi-nm.exe",
]

# 三个新模块头文件导出的公共 API 中，生产代码实际调用、必须出现在 ELF 的部分
REQUIRED_SYMBOLS = [
    "ota_ble_frame_encode", "ota_ble_parser_reset", "ota_ble_parser_feed",
    "ota_ble_demux_init", "ota_ble_demux_feed",
    "ota_ble_ring_init", "ota_ble_ring_push_isr", "ota_ble_ring_pop",
    "ota_ble_session_init", "ota_ble_session_active", "ota_ble_session_isr_active",
    "ota_ble_session_isr_feed", "ota_ble_session_feed_idle", "ota_ble_session_pump",
]

# 已导出但生产侧无调用点的 API：项目开启 -ffunction-sections + -Wl,--gc-sections，
# 链接器丢弃它们是正确行为。但"不在 ELF"也可能是源根本没编译，两者后果完全不同，
# 因此要求在 map 的 Discarded input sections 区找到对应 `.text.<name>` 记录来定性。
GC_ELIGIBLE_SYMBOLS = ["ota_ble_ring_count"]

# 三个新源的对象文件必须出现在 map 中，证明确实参与了本次链接（非孤儿源）
NEW_OBJECTS = ["ota_ble_ring.c.obj", "ota_ble_frame.c.obj", "ota_ble_session.c.obj"]

# host 测试驱动器专有符号，出现在生产 ELF 即说明测试脚手架被误链接
FORBIDDEN_SYMBOLS = [
    "make_full_package", "make_rejection_package", "count_programs_in",
    "run_frame_tests", "run_session_tests", "last_tx", "tx_status",
    "fixture_reset", "expect_ack",
]

NEW_SOURCES = [
    "Libraries/OTA/ota_ble_ring.c",
    "Libraries/OTA/ota_ble_frame.c",
    "Libraries/OTA/ota_ble_session.c",
]
ALLOC_PATTERN = re.compile(r"\b(malloc|calloc|realloc|free|operator\s+new|new\s|delete\s)")

# map 门槛：值来自冻结的链接脚本断言与 P3-1 研究预算
OVERLAY_EXPECT_SIZE = 0xA000     # 链接脚本 SIZEOF(.ota_overlay) 断言值
SESSION_RAM_BUDGET = 650         # 研究文档给出的会话控制块主 RAM 预算(字节)


def find_nm() -> str:
    for cand in NM_CANDIDATES:
        found = shutil.which(cand) or (cand if Path(cand).is_file() else None)
        if found:
            return found
    raise SystemExit("找不到 arm-none-eabi-nm，无法对生产 ELF 取证")


def main() -> int:
    failures: list[str] = []

    if not APP_ELF.is_file() or not APP_MAP.is_file():
        raise SystemExit(f"生产产物缺失: {APP_ELF} / {APP_MAP}")

    nm = find_nm()
    proc = subprocess.run([nm, "--defined-only", str(APP_ELF)],
                          capture_output=True, text=True, check=True)
    sym_names = {line.split()[-1] for line in proc.stdout.splitlines() if line.strip()}
    map_text = APP_MAP.read_text(encoding="utf-8", errors="replace")
    print(f"nm = {nm}")
    print(f"ELF = {APP_ELF.relative_to(ROOT).as_posix()}  已定义符号 {len(sym_names)} 个\n")

    # map 的 Discarded input sections 区间，用于把"被 GC"与"没编译"区分开
    disc_start = map_text.find("\nDiscarded input sections")
    disc_end = map_text.find("\nMemory Configuration")
    if disc_start < 0 or disc_end < 0 or disc_end <= disc_start:
        raise SystemExit("map 中定位不到 Discarded input sections 区间")
    discarded = map_text[disc_start:disc_end]

    # --- 红线 1：新模块公共 API 全部在生产 ELF ---
    missing = [s for s in REQUIRED_SYMBOLS if s not in sym_names]
    ble_syms = sorted(s for s in sym_names if s.startswith("ota_ble_"))
    print(f"[红线1] 生产调用的 BLE 公共 API 应到 {len(REQUIRED_SYMBOLS)} 个，"
          f"缺失 {len(missing)} 个")
    print(f"        生产 ELF 内 ota_ble_* 符号共 {len(ble_syms)} 个")
    for s in missing:
        print(f"        缺失: {s}")
    if missing:
        failures.append(f"新模块 API 未链接进生产 ELF: {missing}")

    # --- 红线 1b：新源对象确实参与链接（排除孤儿源）---
    absent_obj = [o for o in NEW_OBJECTS if o not in map_text]
    print(f"\n[红线1b] P3-1 新源对象在 map 中出现 {len(NEW_OBJECTS) - len(absent_obj)}"
          f"/{len(NEW_OBJECTS)} 个")
    if absent_obj:
        print(f"         未参与链接: {absent_obj}")
        failures.append(f"新源未参与链接: {absent_obj}")

    # --- 红线 1c：允许被 GC 的 API 必须有"编译过但被丢弃"的实证 ---
    print(f"\n[红线1c] 无生产调用点、允许 --gc-sections 回收的 API "
          f"{len(GC_ELIGIBLE_SYMBOLS)} 个")
    for s in GC_ELIGIBLE_SYMBOLS:
        in_elf = s in sym_names
        in_disc = f".text.{s}" in discarded
        if in_elf:
            print(f"         {s}: 仍在 ELF（生产已有调用点，同样合规）")
        elif in_disc:
            print(f"         {s}: 已编译但被链接器丢弃（map Discarded 区可见），合规")
        else:
            print(f"         {s}: 既不在 ELF 也不在 Discarded 区 —— 源可能未编译")
            failures.append(f"{s} 未编译（不在 ELF 亦不在 map Discarded 区）")

    # --- 红线 2：零测试符号 ---
    leaked = [s for s in FORBIDDEN_SYMBOLS if s in sym_names]
    print(f"\n[红线2] 测试专有符号 {len(FORBIDDEN_SYMBOLS)} 个，泄漏 {len(leaked)} 个")
    if leaked:
        print(f"        泄漏: {leaked}")
        failures.append(f"生产 ELF 含测试符号: {leaked}")

    # --- 红线 3：wire 解析零 memcpy ---
    frame_src = (ROOT / "Libraries/OTA/ota_ble_frame.c").read_text(encoding="utf-8")
    memcpy_n = len(re.findall(r"\bmemcpy\b", frame_src))
    print(f"\n[红线3] ota_ble_frame.c 中 memcpy 出现 {memcpy_n} 次（应为 0，须逐字节 LE 组装）")
    if memcpy_n:
        failures.append(f"ota_ble_frame.c 使用 memcpy 解析 wire: {memcpy_n} 次")

    # --- 红线 4：新源零动态分配 ---
    alloc_hits: list[str] = []
    for rel in NEW_SOURCES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if ALLOC_PATTERN.search(line):
                alloc_hits.append(f"{rel}:{lineno}: {line.strip()}")
    print(f"\n[红线4] P3-1 新源动态分配命中 {len(alloc_hits)} 处（应为 0）")
    for h in alloc_hits[:10]:
        print(f"        {h}")
    if alloc_hits:
        failures.append(f"新源存在动态分配: {len(alloc_hits)} 处")

    # --- 红线 5：map RAM 门槛 ---
    m = re.search(r"^\.ota_overlay\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)",
                  map_text, re.MULTILINE)
    overlay_size = int(m.group(2), 16) if m else None
    print(f"\n[红线5a] .ota_overlay 尺寸 = "
          f"{overlay_size if overlay_size is None else hex(overlay_size)}"
          f"（契约断言 {hex(OVERLAY_EXPECT_SIZE)}）")
    if overlay_size != OVERLAY_EXPECT_SIZE:
        failures.append(f".ota_overlay 尺寸偏离断言: {overlay_size}")

    m = re.search(r"^\s*\.bss\._ZL13s_ble_session\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)",
                  map_text, re.MULTILINE)
    session_size = int(m.group(2), 16) if m else None
    print(f"[红线5b] s_ble_session 主 RAM 占用 = "
          f"{session_size if session_size is None else f'{session_size}B'}"
          f"（预算 {SESSION_RAM_BUDGET}B）")
    if session_size is None or session_size > SESSION_RAM_BUDGET:
        failures.append(f"s_ble_session 主 RAM 占用越预算: {session_size}")

    has_a5 = "ota_stack_guard" in map_text and "_user_heap_stack" in map_text
    print(f"[红线5c] A5 栈封顶断言符号在 map 中: {has_a5}（链接成功即断言通过）")
    if not has_a5:
        failures.append("map 中未见 A5 栈封顶断言相关段")

    print(f"\n=== 失败红线 {len(failures)} 项 ===")
    for f in failures:
        print(f"  FAIL: {f}")
    print(f"P3_1_PRODUCTION_BINARY={'PASS' if not failures else 'FAIL'} "
          f"required_api={len(REQUIRED_SYMBOLS)} ble_syms={len(ble_syms)} "
          f"test_syms_leaked={len(leaked)} frame_memcpy={memcpy_n} "
          f"alloc_hits={len(alloc_hits)} overlay_size={overlay_size} "
          f"session_ram={session_size}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
