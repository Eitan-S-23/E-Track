#!/usr/bin/env python3
"""P3-6 独立验收：冻结在证据包内的真实 CI 运行证据核验。

输入只有本卡证据包 `docs/acceptance-contracts/P3-6-v1/ci/` 下由 `gh` 采集的
原始产物（run 元数据 JSON 与被接线步骤的原始日志区段）。脚本不联网，
因此结论可被任何人在离线状态下按同一份包重算。

覆盖任务卡验收字段的三项硬要求：
1. 正例：CI 日志里可见两套测试的实际执行输出与两行标记，计数与 P3-1 基线一致；
2. 反证：注入缺陷的运行变红，且红在被接线的那一步、那一行；
3. 鉴别力归属：同一注错提交上 `Acceptance Governance` 仍绿，说明该缺陷只可能
   被本卡新增的两行抓到。

fail-closed 约定：证据文件缺失、字段缺失、锚点未命中都计失败并非零退出。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_DIR = ROOT / "docs" / "acceptance-contracts" / "P3-6-v1" / "ci"

FIRMWARE_WORKFLOW = "MCU Firmware Build"
GOVERNANCE_WORKFLOW = "Acceptance Governance"
BUILD_JOB = "Build firmware (arm-none-eabi-gcc)"
STEP_NAME = "Test Boot fw_header validator vectors"
STEP_NUMBER = 10

BASELINE_RUN = "33620407886"
DEFECT_RUN = "33621049995"
RESTORE_RUN = "33621403637"
GOVERNANCE_DEFECT_RUN = "33621050015"

BASELINE_HEAD = "0a97b988e2aaab933c827db0ae489706e75b7ef9"
DEFECT_HEAD = "7b58ed6fd8ee5a9124c5d3383c13e57622f4586b"
RESTORE_HEAD = "e3f9b1ab75892ebe06302fe79f0fa41f5014b4ce"

# CI 步骤内应被下发的完整命令序列（末两条为本卡接线）。
EXPECTED_ECHO = (
    "set -euo pipefail",
    "python3 tests/boot/test_fw_header_vectors.py",
    "python3 tests/boot/test_boot_protocols.py",
    "python3 tests/boot/test_boot_state_machine.py",
    "python3 tests/ota/test_ota_staging.py",
    "python3 tests/ota/test_ota_package.py",
    "python3 tests/ota/test_ota_patch.py",
    "python3 tests/ota/test_ota_ble_frame.py",
    "python3 tests/ota/test_ota_ble_session.py",
)
# 位于接线两行之前的既有测试标记；红运行里它们必须照常出现，
# 否则「变红」可能只是环境整体坏掉，不构成接线鉴别力的反证。
PRECEDING_MARKERS = (
    "P1_1_FW_HEADER_VECTORS=PASS",
    "P1_1_BOOT_PROTOCOLS=PASS",
    "P1_3_STATE_MACHINE=PASS",
    "P2_1_STAGING=PASS",
    "P2_2_PACKAGE=PASS",
    "P2_3_VECTOR_PREFLIGHT=PASS",
)
# 任务卡验收字段逐字要求的两行标记（含 P3-1 本地基线的校验点计数）。
FRAME_MARKER = "P3_1_BLE_FRAME=PASS checks=39 failures=0"
SESSION_MARKER = "P3_1_BLE_SESSION=PASS checks=105 failures=0"

# `gh run view --log` 把命令回显的颜色码以脱字符记法 `^[` 落盘（实测原始日志内
# 无 0x1B 字节），故两种形式都要能剥离，避免因转义表示差异误判回显不符。
ANSI_RE = re.compile(r"(?:\x1b|\^\[)\[[0-9;]*[A-Za-z]")
LOG_LINE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T[0-9:.]+Z) ?(.*)$", re.DOTALL)

failures = []
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if condition is not True:
        failures.append(message)


def load_json(name):
    path = CI_DIR / name
    if not path.is_file():
        failures.append(f"证据文件缺失：ci/{name}")
        return None
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        failures.append(f"证据文件不是合法 UTF-8 JSON：ci/{name}（{exc}）")
        return None


def load_step_log(name):
    """解析 `gh run view --log` 的步骤区段，返回 (纯内容行, 列前缀集合)。"""
    path = CI_DIR / name
    if not path.is_file():
        failures.append(f"证据文件缺失：ci/{name}")
        return None, None
    text = path.read_bytes().decode("utf-8-sig")
    contents = []
    prefixes = set()
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if not line:
            continue
        columns = line.split("\t")
        if len(columns) < 3:
            failures.append(f"ci/{name} 出现非 gh 日志格式行：{line[:80]!r}")
            continue
        prefixes.add((columns[0], columns[1]))
        remainder = "\t".join(columns[2:]).lstrip("﻿")
        matched = LOG_LINE_RE.match(remainder)
        if matched is None:
            failures.append(f"ci/{name} 行缺少时间戳：{remainder[:80]!r}")
            continue
        contents.append(ANSI_RE.sub("", matched.group(2)))
    return contents, prefixes


def step_conclusion(run, job_name, step_name):
    for job in run.get("jobs", []):
        if job.get("name") != job_name:
            continue
        for step in job.get("steps", []):
            if step.get("name") == step_name:
                return job.get("conclusion"), step.get("number"), step.get("conclusion")
    return None, None, None


def verify_run_metadata(run_id, expected_head, expected_conclusion, expected_step):
    run = load_json(f"run-{run_id}.json")
    checks_before = len(failures)
    if run is None:
        return None
    check(str(run.get("databaseId")) == run_id, f"run {run_id} databaseId 不符")
    check(run.get("workflowName") == FIRMWARE_WORKFLOW, f"run {run_id} 工作流名不符")
    check(run.get("event") == "pull_request", f"run {run_id} 触发事件不是 pull_request")
    check(run.get("status") == "completed", f"run {run_id} 未完成")
    check(run.get("headSha") == expected_head, f"run {run_id} headSha 不符")
    check(run.get("conclusion") == expected_conclusion, f"run {run_id} 结论不是 {expected_conclusion}")
    job_conclusion, number, conclusion = step_conclusion(run, BUILD_JOB, STEP_NAME)
    check(number == STEP_NUMBER, f"run {run_id} 被接线步骤序号不是 {STEP_NUMBER}：{number}")
    check(conclusion == expected_step, f"run {run_id} 步骤结论不是 {expected_step}：{conclusion}")
    check(job_conclusion == expected_conclusion, f"run {run_id} 构建 job 结论不是 {expected_conclusion}")
    print(
        f"run={run_id} head={str(run.get('headSha'))[:7]} run_conclusion={run.get('conclusion')} "
        f"step{number}={conclusion} new_failures={len(failures) - checks_before}"
    )
    return run


def verify_echo(contents, run_id):
    """`##[group]Run ...` 分组内必须逐条回显 9 行命令，顺序一致。"""
    start = None
    for index, line in enumerate(contents):
        if line.startswith("##[group]Run "):
            start = index
            break
    check(start is not None, f"run {run_id} 日志缺少 ##[group]Run 分组")
    if start is None:
        return
    window = contents[start + 1: start + 1 + len(EXPECTED_ECHO)]
    check(
        tuple(window) == EXPECTED_ECHO,
        f"run {run_id} 命令回显与预期不符：{window}",
    )


def verify_green(run_id, log_name):
    contents, prefixes = load_step_log(log_name)
    if contents is None:
        return
    check(
        prefixes == {(BUILD_JOB, STEP_NAME)},
        f"run {run_id} 日志区段混入了其他 job/step：{sorted(prefixes)}",
    )
    verify_echo(contents, run_id)
    for marker in PRECEDING_MARKERS:
        check(any(line.startswith(marker) for line in contents), f"run {run_id} 缺少既有标记 {marker}")
    check(FRAME_MARKER in contents, f"run {run_id} 缺少帧层标记：{FRAME_MARKER}")
    check(SESSION_MARKER in contents, f"run {run_id} 缺少会话层标记：{SESSION_MARKER}")
    check(
        "=== summary: 39 checks, 0 failure(s) ===" in contents,
        f"run {run_id} 缺少帧层零失败汇总行",
    )
    check(
        "=== summary: 105 checks, 0 failure(s) ===" in contents,
        f"run {run_id} 缺少会话层零失败汇总行",
    )
    check(
        not any("##[error]" in line for line in contents),
        f"run {run_id} 绿运行日志内出现 ##[error]",
    )
    print(f"run={run_id} log_lines={len(contents)} frame_marker=1 session_marker=1")


def verify_red(run_id, log_name):
    contents, prefixes = load_step_log(log_name)
    if contents is None:
        return
    check(
        prefixes == {(BUILD_JOB, STEP_NAME)},
        f"run {run_id} 日志区段混入了其他 job/step：{sorted(prefixes)}",
    )
    verify_echo(contents, run_id)
    # 缺陷必须由被接线的帧层测试抓到，且失败落在该步骤内。
    check(
        "=== summary: 39 checks, 13 failure(s) ===" in contents,
        f"run {run_id} 缺少帧层失败汇总行",
    )
    check(
        any(
            "subprocess.CalledProcessError" in line and "test_ota_ble_frame" in line
            for line in contents
        ),
        f"run {run_id} 缺少帧层非零退出的 CalledProcessError",
    )
    check(
        "##[error]Process completed with exit code 1." in contents,
        f"run {run_id} 步骤未以退出码 1 结束",
    )
    # set -euo pipefail 短路：第二条接线命令不得产生任何输出。
    check(
        not any(line.startswith("P3_1_BLE_FRAME=PASS") for line in contents),
        f"run {run_id} 仍出现帧层 PASS 标记，缺陷未被捕获",
    )
    check(
        not any("P3_1_BLE_SESSION" in line for line in contents),
        f"run {run_id} 出现会话层输出，说明步骤未在首个失败处终止",
    )
    check(
        not any("=== P3-1 BLE session tests ===" in line for line in contents),
        f"run {run_id} 出现会话层分节标题，短路语义不成立",
    )
    # 定界：接线两行之前的 6 条既有测试必须照常通过。
    for marker in PRECEDING_MARKERS:
        check(
            any(line.startswith(marker) for line in contents),
            f"run {run_id} 缺少既有标记 {marker}，无法排除环境整体失败",
        )
    print(f"run={run_id} log_lines={len(contents)} red_at_step={STEP_NUMBER} session_output=0")


def main():
    if not CI_DIR.is_dir():
        print(f"FATAL: 证据目录缺失：{CI_DIR.relative_to(ROOT).as_posix()}", file=sys.stderr)
        return 2

    verify_run_metadata(BASELINE_RUN, BASELINE_HEAD, "success", "success")
    verify_run_metadata(DEFECT_RUN, DEFECT_HEAD, "failure", "failure")
    verify_run_metadata(RESTORE_RUN, RESTORE_HEAD, "success", "success")

    verify_green(BASELINE_RUN, f"step-{BASELINE_RUN}.txt")
    verify_red(DEFECT_RUN, f"step-{DEFECT_RUN}.txt")
    verify_green(RESTORE_RUN, f"step-{RESTORE_RUN}.txt")

    # 鉴别力归属：同一注错提交上治理工作流仍绿。
    governance = load_json(f"run-{GOVERNANCE_DEFECT_RUN}.json")
    if governance is not None:
        check(
            governance.get("workflowName") == GOVERNANCE_WORKFLOW,
            f"run {GOVERNANCE_DEFECT_RUN} 不是 {GOVERNANCE_WORKFLOW}",
        )
        check(governance.get("headSha") == DEFECT_HEAD, "治理运行未落在注错提交上")
        check(governance.get("conclusion") == "success", "注错提交上的治理运行不是 success")
        print(
            f"governance_run={GOVERNANCE_DEFECT_RUN} head={str(governance.get('headSha'))[:7]} "
            f"conclusion={governance.get('conclusion')}"
        )

    # 三次运行必须同属一个 PR 分支，且注错/还原提交仍留在 PR 历史里可复核。
    branch_runs = load_json("runs-branch.json")
    if branch_runs is not None:
        by_id = {str(item.get("databaseId")): item for item in branch_runs}
        for run_id in (BASELINE_RUN, DEFECT_RUN, RESTORE_RUN, GOVERNANCE_DEFECT_RUN):
            check(run_id in by_id, f"分支运行清单缺少 run {run_id}")
            if run_id in by_id:
                check(
                    by_id[run_id].get("event") == "pull_request",
                    f"run {run_id} 在分支清单中不是 pull_request 事件",
                )
        firmware_runs = [
            item for item in branch_runs if item.get("workflowName") == FIRMWARE_WORKFLOW
        ]
        reds = [item for item in firmware_runs if item.get("conclusion") == "failure"]
        check(
            [str(item.get("databaseId")) for item in reds] == [DEFECT_RUN],
            f"分支上除注错运行外还有其他红：{[item.get('databaseId') for item in reds]}",
        )
        print(f"branch_runs={len(branch_runs)} firmware_runs={len(firmware_runs)} reds={len(reds)}")

    pull_request = load_json("pr-14.json")
    if pull_request is not None:
        commits = [str(item.get("oid")) for item in pull_request.get("commits", [])]
        check(pull_request.get("baseRefName") == "main", "PR 基分支不是 main")
        check(pull_request.get("headRefName") == "ota/p3-6-ci-wiring", "PR 头分支不符")
        for head in (BASELINE_HEAD, DEFECT_HEAD, RESTORE_HEAD):
            check(head in commits, f"PR 历史缺少提交 {head[:7]}，反证不可复核")
        check(
            commits.index(DEFECT_HEAD) < commits.index(RESTORE_HEAD),
            "还原提交未排在注错提交之后",
        )
        print(f"pr={pull_request.get('number')} commits={len(commits)} defect_then_restore=1")

    print(f"=== 失败项 {len(failures)} / 核对项 {checks} ===")
    for item in failures:
        print(f"FAIL: {item}")
    status = "PASS" if not failures else "FAIL"
    print(f"P3_6_CI_EVIDENCE={status} checks={checks} failures={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
