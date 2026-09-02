#!/usr/bin/env python3
"""P3-1 验收：冻结命令与冻结日志的忠实性复核。

合同里写的 `command` 字符串如果只是事后追述，整份证据矩阵就退化成自述。
本脚本把每条冻结命令原样重跑一次，与证据包里对应日志逐字节比对，从而把
"该命令确实产出该日志"变成可复算的判据。

归一化范围只允许下列无关差异，其余一律判失败：

1. 行尾 CRLF/LF —— Windows 与 bash 管道混用产生，不含语义。
2. `tempfile.mkdtemp()` 的随机后缀 —— P2-4 回归把 .etu 打进随机临时目录并
   打印绝对路径。
3. `aes_nonce=<32 hex>` —— 打包器每次生成新的随机 nonce。
4. `header_crc32=<8 hex>` —— 该 CRC 覆盖含随机 nonce 的头部，必然随 2 变化。

三处随机量已用两次独立复跑定性：211 行中恒定只有第 195/198/200 行变化，
且互为因果（随机目录、随机 nonce、nonce 派生的 CRC）。掩码按精确正则替换，
只有"差异完全落在被掩码片段内"的行才会归一化后相等，因此掩码不可能吞掉
其他位置的真实回归；被掩码行数会逐条计数打印，便于复核掩码是否越界。

全量 GCC 构建命令代价过高，不在此复跑；其原始 stdout 已直接入证据包，
由 `commands/full-build-raw.log` 自证。

退出码：0=全部命令忠实；1=任一命令产出与冻结日志不符。
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
LOGS = ROOT / "docs/acceptance-contracts/P3-1-v1/commands"

# 掩码 mkdtemp 随机后缀：.cache\etrack-<前缀>-<8位随机>
TEMPDIR_RE = re.compile(rb"(etrack-[0-9a-z-]*?-)[0-9A-Za-z_]{8}(?=[\\/])")
# 掩码打包器每轮新生成的随机 AES nonce，及其派生的头部 CRC32
NONCE_RE = re.compile(rb"(aes_nonce=)[0-9a-f]{32}\b")
HEADER_CRC_RE = re.compile(rb"(header_crc32=)[0-9a-f]{8}\b")

CASES: list[tuple[str, str]] = [
    ("test-ble-frame.log", "python -B tests/ota/test_ota_ble_frame.py"),
    ("test-ble-session.log", "python -B tests/ota/test_ota_ble_session.py"),
    ("test-regression.log",
     "PYTHONIOENCODING=utf-8 bash -c 'for t in test_ota_staging test_ota_package test_ota_sd; "
     "do echo \"### $t.py\"; python -B tests/ota/$t.py 2>&1; echo \"exit=$?\"; echo; done'"),
    ("verify-contract-alignment.log", "python -B tests/ota/p3_1_verify_contract_alignment.py"),
    ("verify-production-binary.log", "python -B tests/ota/p3_1_verify_production_binary.py"),
    ("verify-portability.log", "python -B tests/ota/p3_1_verify_portability.py"),
    ("verify-artifacts.log", "python -B tests/ota/p3_1_verify_artifacts.py"),
    ("verify-text-isolation.log", "python -B tests/ota/p3_1_verify_text_isolation.py"),
    ("verify-mutation.log", "python -B tests/ota/p3_1_verify_mutation.py"),
    ("verify-rx-ring-budget.log", "python -B tests/ota/p3_1_verify_rx_ring_budget.py"),
    ("build-sync-check.log",
     "bash -c 'echo \"### cmake --build (CI 对齐目标，验证产物与当前源同步)\"; "
     "cmake --build MDK-ARM_F435/cmake-generated/build-gcc-release "
     "--target X_Track_App_GCC X_Track_Boot --parallel 2>&1 | tail -1; "
     "echo \"exit=${PIPESTATUS[0]}\"'"),
]


def normalize(data: bytes) -> bytes:
    masked = data.replace(b"\r\n", b"\n")
    masked = TEMPDIR_RE.sub(rb"\1<MKDTEMP>", masked)
    masked = NONCE_RE.sub(rb"\1<RANDOM-NONCE>", masked)
    return HEADER_CRC_RE.sub(rb"\1<NONCE-DERIVED-CRC>", masked)


def masked_line_numbers(produced: bytes, frozen: bytes) -> list[int]:
    """返回"原文不同、掩码后相同"的行号，用于复核掩码是否越界。"""
    got = produced.replace(b"\r\n", b"\n").split(b"\n")
    want = frozen.replace(b"\r\n", b"\n").split(b"\n")
    return [
        index + 1
        for index in range(min(len(got), len(want)))
        if got[index] != want[index] and normalize(got[index]) == normalize(want[index])
    ]


def main() -> int:
    if not LOGS.is_dir():
        raise SystemExit(f"证据包命令日志目录缺失: {LOGS}")

    mismatched: list[str] = []
    masked_total = 0

    for name, command in CASES:
        frozen_path = LOGS / name
        if not frozen_path.is_file():
            print(f"[缺失] {name}")
            mismatched.append(name)
            continue

        proc = subprocess.run(["bash", "-c", command], cwd=ROOT, capture_output=True)
        produced = proc.stdout + proc.stderr
        frozen = frozen_path.read_bytes()

        equal = normalize(produced) == normalize(frozen)
        masked = masked_line_numbers(produced, frozen) if equal else []
        masked_total += len(masked)

        state = "OK  " if equal else "差异"
        note = f"（掩码行 {masked}）" if masked else ""
        print(f"[{state}] {name:34s} exit={proc.returncode} "
              f"复跑 {len(produced)}B / 冻结 {len(frozen)}B "
              f"frozen_sha={hashlib.sha256(frozen).hexdigest()[:12].upper()} {note}")

        if not equal:
            mismatched.append(name)
            got = normalize(produced).decode("utf-8", "replace").splitlines()
            want = normalize(frozen).decode("utf-8", "replace").splitlines()
            print(f"       行数 复跑 {len(got)} / 冻结 {len(want)}")
            for index in range(min(len(got), len(want))):
                if got[index] != want[index]:
                    print(f"       首个差异 行 {index + 1}:")
                    print(f"         复跑: {got[index][:160]}")
                    print(f"         冻结: {want[index][:160]}")
                    break

    print(f"\n=== 命令 {len(CASES)} 条；不忠实 {len(mismatched)} 条；"
          f"随机量掩码行合计 {masked_total} 行 ===")
    for name in mismatched:
        print(f"  FAIL: {name}")
    print(f"P3_1_COMMAND_FIDELITY={'PASS' if not mismatched else 'FAIL'} "
          f"cases={len(CASES)} mismatched={len(mismatched)} masked_lines={masked_total}")
    return 1 if mismatched else 0


if __name__ == "__main__":
    raise SystemExit(main())
