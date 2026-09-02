#!/usr/bin/env python3
"""P3-6 独立验收：改动范围与生产红线的双层核验。

派工书「允许修改范围」「禁止修改与生产红线」是本卡的冻结约束。本脚本在两层
上同时取证，避免只看提交层或只看工作区层造成的盲区：

- 已提交层：合并基点 -> HEAD 的路径集合；
- 工作区层：相对 HEAD 的未提交改动与未跟踪文件。

两层的每一条路径都必须落进带出处标注的授权分层；任何未授权路径即失败。红线
路径（产品源、两套 BLE 测试、他卡验收资产）在两层上都必须零差异。

授权分层按「谁授权的」而不是「谁改的」划分，因此本脚本在看板回写前后都成立，
不依赖执行顺序。
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 派工书「允许修改范围」逐条列出的本卡授权路径。
TIER_CARD = (
    r"^\.github/workflows/firmware-build\.yml$",
    r"^PLAN-OTA-EXEC\.md$",
    r"^docs/ota-exec-notes/P3-6-[^/]+\.md$",
    r"^docs/acceptance-contracts/P3-6-v1\.contract\.json$",
    r"^docs/acceptance-contracts/P3-6-v1/.+$",
)
# 同会话批次 1「治理变更」授权路径：编写派工书并解除 P3-4/P3-6 阻塞，
# 已在看板 §9 变更登记表登记，证据见 docs/ota-exec-notes/P3-6-governance-change.md。
TIER_GOVERNANCE_BATCH1 = (
    r"^docs/ota-prompts/prompt-P3-6-implementation\.md$",
    r"^tests/ota/test_acceptance_bundle\.py$",
    r"^\.gitattributes$",
)
# 本轮独立验收自身产出：核验脚本、评审报告与行尾护栏。
TIER_ACCEPTANCE = (
    r"^tests/ota/p3_6_verify_[a-z_]+\.py$",
    r"^\.claude/verification-report-p3-6\.md$",
    r"^\.gitattributes$",
)
# 分支开工前即存在的未跟踪文件，刻意保持未跟踪（不属本卡产出）。
PREEXISTING_UNTRACKED = (
    ".cache-cmake-time-test.cmake",
    ".claude/cc_recover_s4.js",
    ".claude/ccprobe_hash.js",
    ".claude/ccprobe_plan.js",
    ".claude/write_r5_phase0_board.py",
    ".claude/write_r5_ruling_board.py",
)

# 派工书「禁止修改与生产红线」覆盖的路径前缀，两层都必须零差异。
RED_LINE_PATHSPECS = (
    "ArduinoAPI/",
    "Libraries/",
    "USER/",
    "boot/",
    "cmake/",
    "MDK-ARM_F435/",
    "Simulator/",
    "Tools/",
    "segger_rtt/",
    "vendor/",
    "CMakeLists.txt",
    "build_f435_and_simulator.bat",
    "tests/boot/",
    "tests/ota/test_ota_ble_frame.c",
    "tests/ota/test_ota_ble_frame.py",
    "tests/ota/test_ota_ble_session.c",
    "tests/ota/test_ota_ble_session.py",
    "docs/acceptance-contracts/P3-1-v2.contract.json",
    "docs/acceptance-contracts/P3-1-v2/",
    "docs/acceptance-execution-contract.md",
)
# 被接线的产品源：注错反证后必须逐字节还原，实测值见证据笔记 §4.3。
REVERTED_PRODUCT_SOURCE = "Libraries/OTA/ota_ble_frame.c"
REVERTED_PRODUCT_SHA256 = "07b20f99c37910ccec0cdc8223cea58e7823451a9198f952c30ec98e1003e02a"
# 前置依赖：两套测试必须已在 main 上被跟踪，否则接线在 CI 上必红。
REQUIRED_ON_MAIN = (
    "tests/ota/test_ota_ble_frame.py",
    "tests/ota/test_ota_ble_frame.c",
    "tests/ota/test_ota_ble_session.py",
    "tests/ota/test_ota_ble_session.c",
)

ALL_TIERS = (
    ("card", TIER_CARD),
    ("governance-batch1", TIER_GOVERNANCE_BATCH1),
    ("acceptance", TIER_ACCEPTANCE),
)

failures = []
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if condition is not True:
        failures.append(message)


def git_out(*args, split_null=False):
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        failures.append(f"git {' '.join(args)} 失败：{result.stderr.decode('utf-8', 'replace').strip()[:200]}")
        return None
    text = result.stdout.decode("utf-8")
    if split_null:
        return [item for item in text.split("\0") if item]
    return [line for line in text.replace("\r\n", "\n").split("\n") if line]


def classify(path):
    tiers = [
        name
        for name, patterns in ALL_TIERS
        if any(re.match(pattern, path) for pattern in patterns)
    ]
    return tiers


def main():
    base = git_out("merge-base", "HEAD", "main")
    check(bool(base), "无法解析与 main 的合并基点")
    if not base:
        return report()
    base_sha = base[0].strip()
    print(f"base={base_sha[:12]}")

    # 1. 已提交层：合并基点 -> HEAD。
    committed = git_out("diff", "--name-only", "-z", base_sha, "HEAD", split_null=True) or []
    print(f"committed_changed={len(committed)}")
    for path in sorted(committed):
        tiers = classify(path)
        check(bool(tiers), f"已提交层出现未授权路径：{path}")
        print(f"  [committed] {path} -> {','.join(tiers) or '未授权'}")

    # 2. 工作区层：相对 HEAD 的已跟踪改动 + 未跟踪文件。
    dirty = git_out("diff", "--name-only", "-z", "HEAD", split_null=True) or []
    untracked = git_out("ls-files", "--others", "--exclude-standard", "-z", split_null=True) or []
    print(f"worktree_dirty={len(dirty)} untracked={len(untracked)}")
    for path in sorted(dirty):
        tiers = classify(path)
        check(bool(tiers), f"工作区层出现未授权改动：{path}")
        print(f"  [dirty] {path} -> {','.join(tiers) or '未授权'}")

    preexisting = set(PREEXISTING_UNTRACKED)
    # 未跟踪文件数量随验收证据包逐步落盘而增长，若逐文件各计一项，核对项总数就
    # 依赖执行时刻，日志无法复算。故聚合为一项，失败时把越权路径全部列出。
    unauthorized_untracked = [
        path for path in sorted(untracked) if path not in preexisting and not classify(path)
    ]
    check(not unauthorized_untracked, f"出现未授权的新增未跟踪文件：{unauthorized_untracked}")

    # 开工前即存在的未跟踪文件必须依然未跟踪，且从未被本分支从跟踪中摘除。
    tracked_at_base = set(git_out("ls-tree", "-r", "--name-only", "-z", base_sha, split_null=True) or [])
    for path in PREEXISTING_UNTRACKED:
        check(path in set(untracked), f"预存未跟踪文件状态改变：{path}")
        check(path not in tracked_at_base, f"预存未跟踪文件在基点上是被跟踪的，本分支摘除了它：{path}")

    # 3. 红线路径在两层上都必须零差异。
    red_line_hits = 0
    for pathspec in RED_LINE_PATHSPECS:
        committed_hits = git_out("diff", "--name-only", "-z", base_sha, "HEAD", "--", pathspec, split_null=True)
        dirty_hits = git_out("diff", "--name-only", "-z", "HEAD", "--", pathspec, split_null=True)
        check(committed_hits == [], f"红线路径在已提交层有改动：{pathspec} -> {committed_hits}")
        check(dirty_hits == [], f"红线路径在工作区层有改动：{pathspec} -> {dirty_hits}")
        red_line_hits += len(committed_hits or []) + len(dirty_hits or [])
    print(f"red_line_pathspecs={len(RED_LINE_PATHSPECS)} diffs={red_line_hits}")

    # 4. 注错反证使用的产品源必须逐字节还原（与 main 同字节，且哈希复算一致）。
    worktree_bytes = (ROOT / REVERTED_PRODUCT_SOURCE).read_bytes()
    actual_sha = hashlib.sha256(worktree_bytes).hexdigest()
    blob = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"main:{REVERTED_PRODUCT_SOURCE}"],
        capture_output=True,
        check=False,
    )
    check(blob.returncode == 0, f"无法读取 main:{REVERTED_PRODUCT_SOURCE}")
    check(actual_sha == REVERTED_PRODUCT_SHA256, f"{REVERTED_PRODUCT_SOURCE} 哈希与证据笔记不符：{actual_sha}")
    check(
        blob.returncode == 0 and worktree_bytes == blob.stdout,
        f"{REVERTED_PRODUCT_SOURCE} 工作区字节与 main 不一致，注错未完全还原",
    )
    print(f"reverted_source={REVERTED_PRODUCT_SOURCE} size={len(worktree_bytes)} sha256={actual_sha[:16]}")

    # 5. 前置依赖：被接线的测试文件必须已在 main 上被跟踪。
    main_tracked = set(git_out("ls-tree", "-r", "--name-only", "-z", "main", split_null=True) or [])
    tracked_count = 0
    for path in REQUIRED_ON_MAIN:
        present = path in main_tracked
        check(present, f"被接线的测试文件未在 main 上被跟踪：{path}")
        tracked_count += 1 if present else 0
    print(f"required_on_main={len(REQUIRED_ON_MAIN)} tracked={tracked_count}")

    return report()


def report():
    print(f"=== 失败项 {len(failures)} / 核对项 {checks} ===")
    for item in failures:
        print(f"FAIL: {item}")
    status = "PASS" if not failures else "FAIL"
    print(f"P3_6_SCOPE={status} checks={checks} failures={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
