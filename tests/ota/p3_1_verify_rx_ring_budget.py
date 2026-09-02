#!/usr/bin/env python3
"""P3-1 验收：BLE OTA 接收环尺寸与 overlay 子分配预算的"按实际编译"取证。

看板 P3-1 目标要求「UART 接收缓冲 >=4KB(现 512B)」。源码里存在
`CONFIG_OTA_BLE_RX_RING_SIZE` 并不足以定案：该宏在 `ota_ble_session.h` 里带
`#ifndef` 兜底，真正生效的值取决于生产构型的 `-D` 与 include 顺序。因此本脚本
不读源码字面量，而是取 `compile_commands.json` 里 `ota_ble_session.c` 的**原样
生产编译命令**，用同一套 flag 编译一个探针翻译单元，再从目标文件符号大小反读：

- `CONFIG_OTA_BLE_RX_RING_SIZE` 的实际展开值；
- `sizeof(ota_staging_receiver_t)`（与环共享 overlay workspace）；
- `sizeof(ota_ble_session_t)`（常驻主 RAM 的会话控制块）。

再与生产 map 中 `.ota_overlay` 的真实尺寸联立，核对
`ota_ble_session.c` 在 BEGIN 处的守卫式子分配
（`ws_size < ring + sizeof(receiver)` 即 ERR_BUSY）在生产构型下确实可满足。

探针只写 `.cache/`，不触碰工作区源码，也不改动生产构建目录。

退出码：0=全部预算判据满足；1=任一判据不满足或取证失效。
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "MDK-ARM_F435/cmake-generated/build-gcc-release"
CCDB = BUILD / "compile_commands.json"
APP_MAP = BUILD / "app-gcc/X-Track-App-GCC.map"
WORK = ROOT / ".cache/p3-1-acceptance/ring-probe"

TARGET_TU = "Libraries/OTA/ota_ble_session.c"

# 合同 §5.1 冻结要求：BLE OTA 接收缓冲不小于 4KB
RING_MIN_BYTES = 4096

PROBE_SOURCE = """/* P3-1 验收探针：只用符号大小把编译期常量搬到目标文件里，无运行时代码。 */
#include "OTA/ota_ble_session.h"

unsigned char p3_1_probe_ring[CONFIG_OTA_BLE_RX_RING_SIZE];
unsigned char p3_1_probe_receiver[sizeof(ota_staging_receiver_t)];
unsigned char p3_1_probe_session[sizeof(ota_ble_session_t)];
"""

# 探针不产生依赖文件，也不复用生产对象路径，故剔除输出/依赖类参数
DROP_WITH_VALUE = {"-o", "-MT", "-MF", "-MQ"}
DROP_FLAGS = {"-c", "-MD", "-MMD", "-MP"}


def split_command(command: str) -> list[str]:
    """按 shell 规则切分 compile_commands.json 的 command 字段。"""
    import shlex

    return shlex.split(command, posix=False)


def strip_quotes(token: str) -> str:
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'":
        return token[1:-1]
    return token


def find_nm() -> str:
    candidates = [
        "arm-none-eabi-nm",
        r"D:/singlechip/gcc+gdb+openocd/tools/arm-gnu-toolchain-13.3.rel1-ming/bin/arm-none-eabi-nm.exe",
    ]
    for cand in candidates:
        found = shutil.which(cand) or (cand if Path(cand).is_file() else None)
        if found:
            return found
    raise SystemExit("找不到 arm-none-eabi-nm，无法从探针目标文件反读常量")


def main() -> int:
    failures: list[str] = []

    if not CCDB.is_file():
        raise SystemExit(f"缺少生产编译数据库: {CCDB}")
    if not APP_MAP.is_file():
        raise SystemExit(f"缺少生产链接 map: {APP_MAP}")

    entries = json.loads(CCDB.read_text(encoding="utf-8"))
    matches = [e for e in entries if e["file"].replace("\\", "/").endswith(TARGET_TU)]
    if len(matches) != 1:
        raise SystemExit(f"{TARGET_TU} 在编译数据库中命中 {len(matches)} 条，无法唯一取证")
    entry = matches[0]

    tokens = split_command(entry["command"])
    compiler = strip_quotes(tokens[0])
    source_abs = Path(entry["file"]).as_posix().lower()

    flags: list[str] = []
    skip_next = False
    for token in tokens[1:]:
        if skip_next:
            skip_next = False
            continue
        bare = strip_quotes(token)
        if bare in DROP_WITH_VALUE:
            skip_next = True
            continue
        if bare in DROP_FLAGS:
            continue
        if bare.replace("\\", "/").lower() == source_abs:
            continue
        flags.append(bare)

    WORK.mkdir(parents=True, exist_ok=True)
    probe_c = WORK / "p3_1_ring_probe.c"
    probe_o = WORK / "p3_1_ring_probe.o"
    probe_c.write_text(PROBE_SOURCE, encoding="utf-8", newline="\n")
    if probe_o.exists():
        probe_o.unlink()

    argv = [compiler, *flags, "-c", str(probe_c), "-o", str(probe_o)]
    proc = subprocess.run(argv, cwd=entry["directory"], capture_output=True, text=True)
    print(f"编译器 = {compiler}")
    print(f"取证 TU = {TARGET_TU}（生产 flag 原样复用 {len(flags)} 个）")
    print(f"探针目标 = {probe_o.relative_to(ROOT).as_posix()}  exit={proc.returncode}")
    if proc.returncode != 0 or not probe_o.is_file():
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit("探针编译失败，无法取证（判据 fail-closed）")

    nm = find_nm()
    out = subprocess.run([nm, "-S", "--defined-only", str(probe_o)],
                         capture_output=True, text=True, check=True).stdout
    sizes: dict[str, int] = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4:
            sizes[parts[3]] = int(parts[1], 16)

    ring = sizes.get("p3_1_probe_ring")
    receiver = sizes.get("p3_1_probe_receiver")
    session = sizes.get("p3_1_probe_session")
    if ring is None or receiver is None or session is None:
        raise SystemExit(f"探针符号大小读取失败: {sizes}")

    map_text = APP_MAP.read_text(encoding="utf-8", errors="replace")
    import re

    m = re.search(r"^\.ota_overlay\s+(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)",
                  map_text, re.MULTILINE)
    overlay = int(m.group(2), 16) if m else None
    if overlay is None:
        raise SystemExit("map 中读不到 .ota_overlay 尺寸")

    print(f"\n[实测] CONFIG_OTA_BLE_RX_RING_SIZE = {ring}B（按生产 flag 展开）")
    print(f"[实测] sizeof(ota_staging_receiver_t) = {receiver}B")
    print(f"[实测] sizeof(ota_ble_session_t) = {session}B")
    print(f"[实测] map .ota_overlay = {overlay}B\n")

    # --- 判据 1：合同 §5.1 的 >=4KB ---
    print(f"[判据1] 接收环 >= {RING_MIN_BYTES}B: {ring >= RING_MIN_BYTES}")
    if ring < RING_MIN_BYTES:
        failures.append(f"接收环 {ring}B 小于合同要求的 {RING_MIN_BYTES}B")

    # --- 判据 2：环尺寸须为 2 的幂（ota_ble_ring_init 的掩码回绕前提）---
    power_of_two = ring > 0 and (ring & (ring - 1)) == 0
    print(f"[判据2] 环尺寸为 2 的幂（掩码回绕前提）: {power_of_two}")
    if not power_of_two:
        failures.append(f"接收环 {ring}B 不是 2 的幂，ota_ble_ring_init 将 fail-closed")

    # --- 判据 3：环 + receiver 必须放得进 overlay，否则 BEGIN 恒 ERR_BUSY ---
    need = ring + receiver
    print(f"[判据3] 环 + receiver = {need}B <= overlay {overlay}B: {need <= overlay}"
          f"（余量 {overlay - need}B）")
    if need > overlay:
        failures.append(f"overlay 放不下环+receiver: 需 {need}B，实有 {overlay}B")

    print(f"\n=== 失败判据 {len(failures)} 项 ===")
    for item in failures:
        print(f"  FAIL: {item}")
    print(f"P3_1_RX_RING_BUDGET={'PASS' if not failures else 'FAIL'} "
          f"ring={ring} receiver={receiver} session_obj={session} "
          f"overlay={overlay} headroom={overlay - need}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
