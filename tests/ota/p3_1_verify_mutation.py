#!/usr/bin/env python3
"""P3-1 验收：harness 鉴别力变异测试（fail-closed 证明）。

`docs/acceptance-execution-contract.md` §7 要求 harness 必须由原始观测计算、
禁止常量 PASS，并"至少包含一个证明判据具有鉴别力的负例或故障注入"。
"测试全绿"本身无法证明这一点——一个恒返回 PASS 的 harness 同样全绿。

因此本脚本把产品缺陷注入到 `.cache` 下的源码副本，重新编译 host 测试并观察
是否变红。工作区源文件全程只读，不被修改。

变异 M3 预期为等价变异：R8-4 幂等由 staging 与 session 双层实现，单独禁用
session 层短路后外部可观测协议行为不变，测试保持绿色是正确的。M5 同时禁用
两层以证明该行为整体确实被测试锁定。

退出码：0=每个有效变异都被检出（等价变异除外）；1=存在漏检。
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
MUT_ROOT = ROOT / ".cache/p3-1-acceptance/mutation"

CC = shutil.which("gcc") or shutil.which("cc")
# 变异副本脱离原目录，`#include "ota_staging.h"` 这类同目录引用会失效，
# 故显式补上 Libraries/OTA 搜索路径。
BASE_FLAGS = ["-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
              f"-I{ROOT / 'Libraries'}", f"-I{ROOT / 'Libraries/OTA'}",
              f"-I{ROOT / 'boot/include'}"]

FRAME_SRC = ["tests/ota/test_ota_ble_frame.c",
             "Libraries/OTA/ota_ble_frame.c", "Libraries/OTA/ota_ble_ring.c"]
SESSION_SRC = ["tests/ota/test_ota_ble_session.c",
               "Libraries/OTA/ota_ble_session.c",
               "Libraries/OTA/ota_ble_frame.c", "Libraries/OTA/ota_ble_ring.c",
               "Libraries/OTA/ota_sd.c", "Libraries/OTA/ota_staging.c",
               "boot/src/boot_crc32.c", "boot/src/boot_sha256.c"]

SESSION_C = "Libraries/OTA/ota_ble_session.c"
STAGING_C = "Libraries/OTA/ota_staging.c"
FRAME_C = "Libraries/OTA/ota_ble_frame.c"

# 单个变异 = (id, 说明, [(目标源, 原文, 变异文), ...], 源清单, 是否预期等价变异)
MUTATIONS = [
    ("M1-crc-poly", "CRC16 多项式偏离契约 0x1021",
     [(FRAME_C, "crc = (uint16_t)((crc << 1) ^ 0x1021u);",
       "crc = (uint16_t)((crc << 1) ^ 0x1022u);")],
     FRAME_SRC, False),
    ("M2-seq-wrap", "seq 16bit 回绕比较退化为无符号比较",
     [(SESSION_C, "int16_t delta = (int16_t)(uint16_t)(seq - session->expected_seq);",
       "int32_t delta = (int32_t)seq - (int32_t)session->expected_seq;")],
     SESSION_SRC, False),
    ("M3-session-idempotent", "仅禁用 session 层 off<durable_off 幂等短路",
     [(SESSION_C, "if (off < session->progress.durable_off)",
       "if (off < session->progress.durable_off && session->total_len == 0u)")],
     SESSION_SRC, True),
    ("M4-end-sha-gate", "END 整包 SHA-256 复核门禁被短路",
     [(SESSION_C, "if (memcmp(digest, session->package_sha256, 32u) != 0)",
       "if (memcmp(digest, session->package_sha256, 32u) != 0 && 0)")],
     SESSION_SRC, False),
    ("M5-both-idempotent", "同时禁用 session 层短路与 staging 层幂等(R8-4 双层)",
     [(SESSION_C, "if (off < session->progress.durable_off)",
       "if (off < session->progress.durable_off && session->total_len == 0u)"),
      (STAGING_C, "if (offset < receiver->durable_off)",
       "if (offset < receiver->durable_off && 0)")],
     SESSION_SRC, False),
]


def run_one(mid, desc, edits, srcs, equivalent):
    mut_dir = MUT_ROOT / mid
    mut_dir.mkdir(parents=True, exist_ok=True)
    replaced: dict[str, Path] = {}
    anchor_counts: list[int] = []

    for target, old, new in edits:
        text = (ROOT / target).read_text(encoding="utf-8")
        count = text.count(old)
        anchor_counts.append(count)
        if count == 0:
            return mid, "ANCHOR_MISSING", anchor_counts, f"锚点不存在于 {target}"
        mut_file = mut_dir / Path(target).name
        mut_file.write_text(text.replace(old, new), encoding="utf-8")
        replaced[target] = mut_file

    sources = [str(replaced.get(s, ROOT / s)) for s in srcs]
    exe = mut_dir / f"{mid}.exe"
    build = subprocess.run([CC, *BASE_FLAGS, *sources, "-o", str(exe)],
                           cwd=ROOT, capture_output=True, text=True)
    if build.returncode != 0:
        return mid, "BUILD_FAIL", anchor_counts, build.stderr.strip()[:300]

    proc = subprocess.run([str(exe)], cwd=ROOT, capture_output=True, text=True)
    detected = proc.returncode != 0
    fails = [ln.strip() for ln in proc.stdout.splitlines() if "FAIL" in ln]
    if equivalent:
        verdict = "EQUIVALENT(预期不变红)" if not detected else "EQUIVALENT_BUT_DETECTED"
    else:
        verdict = "DETECTED(测试变红)" if detected else "MISSED(测试仍绿!)"
    return mid, verdict, anchor_counts, "; ".join(fails[-3:])[:300]


def main() -> int:
    if CC is None:
        raise SystemExit("找不到 gcc/cc，无法执行变异测试")
    print(f"CC = {CC}")
    print(f"变异副本目录 = {MUT_ROOT.relative_to(ROOT).as_posix()}（.gitignore 内，不入证据包）")
    print(f"工作区源文件全程只读\n")

    effective_total = 0
    effective_detected = 0
    problems = 0
    for mid, desc, edits, srcs, equivalent in MUTATIONS:
        m, verdict, counts, detail = run_one(mid, desc, edits, srcs, equivalent)
        print(f"[{m}] {desc}")
        print(f"  变异点 {len(edits)} 处，锚点命中 {counts} -> {verdict}")
        if detail:
            print(f"  {detail}")
        if not equivalent:
            effective_total += 1
            if verdict.startswith("DETECTED"):
                effective_detected += 1
            else:
                problems += 1
        elif verdict != "EQUIVALENT(预期不变红)":
            problems += 1
        print()

    ok = problems == 0
    print(f"=== 有效变异检出 {effective_detected}/{effective_total}；"
          f"等价变异 {len(MUTATIONS) - effective_total} 项按预期不变红 ===")
    print(f"P3_1_MUTATION={'PASS' if ok else 'FAIL'} "
          f"effective_detected={effective_detected} effective_total={effective_total} "
          f"problems={problems}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
