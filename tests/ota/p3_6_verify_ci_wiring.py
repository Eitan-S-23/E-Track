#!/usr/bin/env python3
"""P3-6 独立验收：workflow 接线位置与 fail-closed 结构的静态核验。

只读仓库内文本与 git 对象，不联网、不构建。回答任务卡验收字段中
「接线落在 `set -euo pipefail` 保护的测试步骤内、且未被任何忽略退出码的
子句削弱、且触发器未被改动」这一半；CI 是否真的跑过由
`p3_6_verify_ci_evidence.py` 用冻结日志回答。

fail-closed 约定：任何检查项无法取证即计失败，退出码非零；不存在
「没有报错就算过」的分支。
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ".github/workflows/firmware-build.yml"
STEP_NAME = "Test Boot fw_header validator vectors"

# 派工书「现有组件和代码入口」列明的既有 6 条命令，顺序即步骤内顺序。
BASELINE_COMMANDS = (
    "python3 tests/boot/test_fw_header_vectors.py",
    "python3 tests/boot/test_boot_protocols.py",
    "python3 tests/boot/test_boot_state_machine.py",
    "python3 tests/ota/test_ota_staging.py",
    "python3 tests/ota/test_ota_package.py",
    "python3 tests/ota/test_ota_patch.py",
)
# 本卡要求新增的两条，必须出现且必须在同一步骤内。
WIRED_COMMANDS = (
    "python3 tests/ota/test_ota_ble_frame.py",
    "python3 tests/ota/test_ota_ble_session.py",
)
# 派工书「禁止修改与生产红线」逐条列出的 fail-closed 削弱写法。
FORBIDDEN_PATTERNS = (
    "|| true",
    "continue-on-error",
    "if: always()",
    "set +e",
    "|| :",
    "exit 0",
)

failures = []
checks = 0


def check(condition, message):
    """记录一条判定；condition 必须是已求值的布尔量。"""
    global checks
    checks += 1
    if condition is not True:
        failures.append(message)


def read_lines(text):
    return [line.rstrip("\r") for line in text.split("\n")]


def git_show(revision, repo_path):
    result = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{revision}:{repo_path}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8")


def resolve_base():
    """取本分支与 main 的合并基点；无法解析即失败，不静默放行。"""
    for candidate in ("main", "origin/main"):
        result = subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "HEAD", candidate],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.decode("utf-8").strip(), candidate
    return None, None


def extract_step(lines, step_name):
    """按缩进抽取指定 name 的步骤块与其 run 脚本行。"""
    marker = f"- name: {step_name}"
    start = None
    indent = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == marker:
            start = index
            indent = len(line) - len(line.lstrip(" "))
            break
    if start is None:
        return None, None, None

    block = [lines[start]]
    for line in lines[start + 1:]:
        if not line.strip():
            block.append(line)
            continue
        current_indent = len(line) - len(line.lstrip(" "))
        if current_indent <= indent and line.strip().startswith("- "):
            break
        if current_indent <= indent - 2:
            break
        block.append(line)

    run_lines = None
    for index, line in enumerate(block):
        if line.strip() == "run: |":
            run_indent = len(line) - len(line.lstrip(" "))
            collected = []
            for candidate in block[index + 1:]:
                if not candidate.strip():
                    collected.append("")
                    continue
                if len(candidate) - len(candidate.lstrip(" ")) <= run_indent:
                    break
                collected.append(candidate.strip())
            run_lines = [item for item in collected if item]
            break
    return block, run_lines, indent


def slice_trigger_section(lines):
    """截取 `on:` 到 `jobs:` 之前的触发器段。"""
    start = None
    end = None
    for index, line in enumerate(lines):
        if line.rstrip() == "on:":
            start = index
        elif start is not None and re.match(r"^[A-Za-z_]+:", line):
            end = index
            break
    if start is None:
        return None
    return lines[start:end if end is not None else len(lines)]


def report():
    print(f"=== 失败项 {len(failures)} / 核对项 {checks} ===")
    for item in failures:
        print(f"FAIL: {item}")
    status = "PASS" if not failures else "FAIL"
    print(f"P3_6_CI_WIRING={status} checks={checks} failures={len(failures)}")
    return 0 if not failures else 1


def main():
    workflow_path = ROOT / WORKFLOW
    if not workflow_path.is_file():
        print(f"FATAL: workflow not found: {WORKFLOW}", file=sys.stderr)
        return 2
    raw = workflow_path.read_bytes()
    text = raw.decode("utf-8")
    lines = read_lines(text)
    print(f"workflow={WORKFLOW} size={len(raw)}")

    block, run_lines, _ = extract_step(lines, STEP_NAME)
    check(block is not None, f"未找到步骤 `{STEP_NAME}`")
    check(run_lines is not None and bool(run_lines), "步骤缺少 run 脚本块")
    if not run_lines:
        return report()

    # 1. 步骤内命令序列必须精确等于「6 条既有 + 2 条新增」，且 shell 守卫在首行。
    expected = ["set -euo pipefail"] + list(BASELINE_COMMANDS) + list(WIRED_COMMANDS)
    check(run_lines == expected, f"步骤命令序列不符：{run_lines}")
    check(run_lines[0] == "set -euo pipefail", "步骤首行必须是 set -euo pipefail")
    guard_index = run_lines.index("set -euo pipefail") if "set -euo pipefail" in run_lines else None
    for command in WIRED_COMMANDS:
        present = command in run_lines
        check(present, f"缺少接线命令：{command}")
        # 缺守卫或缺命令时不再谈「谁在谁之后」，但仍必须计一项失败，不得静默跳过。
        check(
            present and guard_index is not None and run_lines.index(command) > guard_index,
            f"接线命令未落在 set -euo pipefail 之后：{command}",
        )
    print(f"step_commands={len(run_lines)} wired={len(WIRED_COMMANDS)}")

    # 2. 该步骤块本身不得带条件执行或忽略失败的键。
    block_text = "\n".join(block)
    check("continue-on-error" not in block_text, "接线步骤带 continue-on-error")
    check(
        not re.search(r"^\s*if:", block_text, re.MULTILINE),
        "接线步骤带 if: 条件，可能被跳过",
    )
    for command in WIRED_COMMANDS:
        for line in run_lines:
            if line.startswith(command):
                check(line == command, f"接线命令被额外子句包裹：{line}")

    # 3. 整个 workflow 不得出现任何 fail-closed 削弱写法。
    for pattern in FORBIDDEN_PATTERNS:
        hits = [
            index + 1
            for index, line in enumerate(lines)
            if pattern in line and not line.strip().startswith("#")
        ]
        check(not hits, f"workflow 出现 fail-closed 削弱写法 {pattern!r} 于行 {hits}")

    # 4. 本卡裁定「p3_1_verify_*.py 一个都不接入」，workflow 内不得出现其名。
    check(
        "p3_1_verify" not in text,
        "workflow 出现 p3_1_verify_*，与本卡分类裁定冲突",
    )

    # 5. 触发器段必须与合并基点逐行一致（派工书非目标：不改触发器）。
    base_sha, base_ref = resolve_base()
    check(base_sha is not None, "无法解析与 main 的合并基点")
    if base_sha:
        base_text = git_show(base_sha, WORKFLOW)
        check(base_text is not None, f"无法读取基点版本：{base_sha[:12]}:{WORKFLOW}")
        if base_text is not None:
            base_lines = read_lines(base_text)
            current_trigger = slice_trigger_section(lines)
            base_trigger = slice_trigger_section(base_lines)
            check(current_trigger is not None, "当前版本缺少 on: 段")
            check(base_trigger is not None, "基点版本缺少 on: 段")
            check(current_trigger == base_trigger, "触发器段相对基点发生改动")
            trigger_len = len(current_trigger or [])
            print(f"base={base_sha[:12]} base_ref={base_ref} trigger_lines={trigger_len}")

            # 触发器必须已覆盖被接线的两套测试与其产品源，否则接线形同虚设。
            trigger_text = "\n".join(current_trigger or [])
            for needle in ('"tests/ota/test_ota_*.py"', '"Libraries/**"', '"' + WORKFLOW + '"'):
                check(needle in trigger_text, f"触发器缺少必要 path：{needle}")

            # 6. 相对基点的 diff 必须是纯新增两行，无夹带。
            numstat = subprocess.run(
                ["git", "-C", str(ROOT), "diff", "--numstat", base_sha, "--", WORKFLOW],
                capture_output=True,
                check=False,
            )
            check(numstat.returncode == 0, "git diff --numstat 执行失败")
            stat_text = numstat.stdout.decode("utf-8").strip()
            check(
                stat_text.split("\t")[:2] == ["2", "0"],
                f"workflow diff 不是纯新增两行：{stat_text!r}",
            )
            diff = subprocess.run(
                ["git", "-C", str(ROOT), "diff", "-U0", base_sha, "--", WORKFLOW],
                capture_output=True,
                check=False,
            )
            check(diff.returncode == 0, "git diff -U0 执行失败")
            diff_lines = read_lines(diff.stdout.decode("utf-8"))
            added = [
                line[1:].strip()
                for line in diff_lines
                if line.startswith("+") and not line.startswith("+++")
            ]
            removed = [
                line[1:].strip()
                for line in diff_lines
                if line.startswith("-") and not line.startswith("---")
            ]
            check(added == list(WIRED_COMMANDS), f"新增行不是两条接线命令：{added}")
            check(not removed, f"存在删除行：{removed}")
            print(f"diff_numstat={stat_text!r} added={len(added)} removed={len(removed)}")

    return report()


if __name__ == "__main__":
    sys.exit(main())
