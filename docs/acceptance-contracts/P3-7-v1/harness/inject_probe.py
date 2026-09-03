"""P3-7 验收 harness 鉴别力反证：对 workflow 单点注错，确认核验器红在对应判据。

安全性：本脚本**不使用** `git checkout --`（工作树相对 HEAD 正持有实现方未提交的
改动，checkout 会连实现成果一起抹掉）。改为先把当前字节存档到 .cache，注错后
用存档字节还原，并逐次以 SHA-256 核对还原结果。任一还原失败即抛异常中止。
"""

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path("D:/github/my/E-Track")
WF = ROOT / ".github/workflows/firmware-build.yml"
BACKUP = ROOT / ".cache/p3-7-accept/firmware-build.yml.orig"
VERIFIER = ROOT / "tests/ota/p3_7_verify_wiring.py"

ORIG = WF.read_bytes()
ORIG_SHA = hashlib.sha256(ORIG).hexdigest().upper()
BACKUP.parent.mkdir(parents=True, exist_ok=True)
BACKUP.write_bytes(ORIG)
assert hashlib.sha256(BACKUP.read_bytes()).hexdigest().upper() == ORIG_SHA
print(f"原始字节存档 len={len(ORIG)} sha256={ORIG_SHA}")

# 每项：标签、被替换的字节串、替换成的字节串、锚点应出现的次数、预期变红的判据关键词。
# 次数为 2 表示 push / pull_request 两份列表都含该串；replace(..., 1) 只改前者
# （已实测 push 列表在文件中位于 pull_request 之前），从而制造「两份失同步」。
CASES = [
    (
        "I1 执行行加 || true（削弱 fail-closed）",
        b"          python3 tests/ota/p3_1_verify_portability.py\n",
        b"          python3 tests/ota/p3_1_verify_portability.py || true\n",
        1,
        ["fail-open", "未被额外子句包裹", "命令序列"],
    ),
    (
        "I2 只删 push.paths 的一个新增条目（两份列表失同步）",
        b'      - "tests/ota/p3_1_verify_text_isolation.py"\n      - "tests/ota/p3_1_verify_portability.py"\n',
        b'      - "tests/ota/p3_1_verify_portability.py"\n',
        2,
        ["逐项相等", "push.paths 含精确条目", "新增恰为三条"],
    ),
    (
        "I3 删掉一条执行行（接线不全）",
        b"          python3 tests/ota/p3_1_verify_text_isolation.py\n",
        b"",
        1,
        ["命令序列", "执行行计数", "接线命令存在"],
    ),
    (
        "I4 新增条目改成通配（触发范围溢出到不接入脚本）",
        b'      - "tests/ota/p3_1_verify_contract_alignment.py"\n      - "tests/ota/p3_1_verify_text_isolation.py"\n      - "tests/ota/p3_1_verify_portability.py"\n',
        b'      - "tests/ota/p3_1_verify_*.py"\n',
        2,
        ["逐项相等", "新增恰为三条", "未覆盖不接入脚本"],
    ),
    (
        "I5 改 jobs.build.name（红线：分支必需检查按它识别）",
        b"    name: Build firmware (arm-none-eabi-gcc)",
        b"    name: Build firmware (gcc)",
        1,
        ["jobs.build.name"],
    ),
    # 以下三项针对派工书 v2 新增的第 4 条接线（cmd12 走既有通配覆盖，paths 零改动）。
    # v1 的 I1-I5 不触及这些判据，必须单独证明它们有鉴别力。
    (
        "I6 删掉第 4 条执行行（v2 接线不全）",
        b"          python3 tests/ota/test_ota_device_info.py\n",
        b"",
        1,
        ["命令序列", "执行行计数", "接线命令存在"],
    ),
    (
        "I7 只删 push.paths 的既有通配（cmd12 覆盖失效）",
        b'      - "tests/ota/test_ota_*.py"\n',
        b"",
        2,
        ["逐项相等", "既有通配仍在两份 paths 内"],
    ),
    (
        "I8 为已被通配覆盖的脚本加冗余精确条目（paths 非零改动）",
        b'      - "tests/ota/test_ota_*.py"\n',
        b'      - "tests/ota/test_ota_*.py"\n      - "tests/ota/test_ota_device_info.py"\n',
        2,
        ["逐项相等", "冗余精确条目", "新增恰为三条"],
    ),
]


def run_verifier():
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(VERIFIER)],
        capture_output=True,
        check=False,
        cwd=str(ROOT),
    )
    out = result.stdout.decode("utf-8", "replace")
    reds = [line.strip()[5:] for line in out.split("\n") if line.strip().startswith("FAIL ")]
    marker = [line for line in out.split("\n") if line.startswith("P3_7_WIRING=")]
    return result.returncode, reds, (marker[0] if marker else "<无结论标记>")


rc, reds, marker = run_verifier()
print(f"\n[基线] rc={rc} {marker}")
for item in reds:
    print(f"   红: {item}")
BASELINE_REDS = set(reds)

summary = []
for label, needle, replacement, want_count, expects in CASES:
    assert ORIG.count(needle) == want_count, (
        f"{label}: 注入锚点次数不符（实际 {ORIG.count(needle)}，预期 {want_count}）"
    )
    WF.write_bytes(ORIG.replace(needle, replacement, 1))
    rc_bad, reds_bad, marker_bad = run_verifier()
    new_reds = [r for r in reds_bad if r.split(":")[0] not in {x.split(":")[0] for x in BASELINE_REDS}]
    hit = {kw: any(kw in r for r in new_reds) for kw in expects}
    print(f"\n[{label}] rc={rc_bad} {marker_bad}")
    for item in new_reds:
        print(f"   新红: {item[:150]}")
    print(f"   预期关键词命中: {hit}")
    # 还原并核对字节
    WF.write_bytes(BACKUP.read_bytes())
    back_sha = hashlib.sha256(WF.read_bytes()).hexdigest().upper()
    assert back_sha == ORIG_SHA, f"{label}: 还原后字节不一致 {back_sha}"
    rc_back, reds_back, marker_back = run_verifier()
    assert set(reds_back) == BASELINE_REDS, f"{label}: 还原后红项集合与基线不同 {reds_back}"
    summary.append(
        (label, rc_bad, len(new_reds), all(hit.values()), rc_back == rc, back_sha == ORIG_SHA)
    )
    print(f"   还原: rc={rc_back} 字节一致=True 红项集合复原=True")

print("\n=== 反证汇总 ===")
ok = True
for label, rc_bad, n_new, all_hit, rc_same, byte_same in summary:
    status = "OK" if (rc_bad == 1 and n_new > 0 and all_hit and rc_same and byte_same) else "BAD"
    if status == "BAD":
        ok = False
    print(f"{status} {label} rc={rc_bad} 新红={n_new} 关键词全命中={all_hit}")
print(f"P3_7_HARNESS_DISCRIMINATION={'PASS' if ok else 'FAIL'} cases={len(summary)}")
sys.exit(0 if ok else 1)
