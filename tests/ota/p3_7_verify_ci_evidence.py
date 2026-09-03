#!/usr/bin/env python3
"""P3-7 独立验收：冻结在证据包内的真实 CI 运行证据核验（派工书 v2，四条接线）。

输入只有 `docs/acceptance-contracts/P3-7-v1/ci/` 下由 `gh` 采集的原始产物
（run 元数据 JSON、被接线步骤的原始日志区段、每个 run 对应提交的改动文件清单、
正例 run 处的 workflow 原文、PR 元数据）。脚本不联网，结论可离线按同一份包重算。

覆盖派工书「完成判据」里本机静态核验无法回答的四项：
1. 正例：CI 日志出现四条脚本的实际执行输出与结论标记，判据计数与立卡基线一致；
2. 触发器反证：一次**只改被接入脚本自身**的推送确实触发本工作流并执行到脚本。
   本卡有两类 paths 覆盖，必须各自反证：
     * 新增精确条目（cmd9-cmd11 三条 `p3_1_verify_*.py`）；
     * 既有通配 `tests/ota/test_ota_*.py`（cmd12 的 `test_ota_device_info.py`
       未新增精确条目，其覆盖由该通配承担）。本机静态断言用的是本仓库自实现的
       glob 匹配，不是 GitHub 的实现，所以这条覆盖只能由真实 CI 触发来证明。
3. 四次 fail-closed 反证：注入 -> 红 -> 还原 -> 绿，且红必须落在本卡新增的那一行；
4. 定界：红运行里位于新增四行**之前**的 8 条既有测试全部照常通过。

第 4 项不是锦上添花，而是本卡反证有效性的充要条件。步骤在 `set -euo pipefail`
下线性执行，若注入的缺陷同时破坏了前 8 条既有测试中的任何一条，步骤会在那一条
就短路变红，新增行根本不会执行——这样的「红」与本卡接线无关，不构成反证。
已实测三个无效选点（均先红在第 8 条 `test_ota_ble_frame.py` 或
`test_ota_ble_session.py`）：
  * 改 `Libraries/OTA/ota_ble_frame.h` 的 `OTA_BLE_SYNC0`：
    `tests/ota/test_ota_ble_frame.c` 直接使用该宏并硬编码 `0xA5u`；
  * 往 `Libraries/OTA/ota_ble_ring.h` 插反斜杠 `#include`：
    同一个 C 用例 `#include "OTA/ota_ble_ring.h"`，Linux 上先编译失败；
  * 改 `OTA_BLE_LEN_ACK_OTHER` 9u->8u（本会话第 1 轮曾错误开出此选点）：
    `Libraries/OTA/ota_ble_session.c` 用它作数组维度，`-Werror=array-bounds`
    在第 8 条 `test_ota_ble_session.py` 编译期即触发。
   最后一条的教训是通用的：选点安全性必须按**前置命令的传递编译集**判定，
   只扫 `tests/` 下的文本引用会漏掉产品翻译单元。
因此本脚本对每个红运行都强制核对全部前置标记，无效选点会被判失败而非通过。

红绿因果归属：每个红/绿 run 都要绑定其提交的改动文件清单，且必须恰为该次
反证的冻结注错目标文件。残留局限（如实登记，不隐瞒）：本脚本只比对文件**路径**
集合，不比对该文件在红/绿两次提交处的 blob 哈希，故「还原提交确实把内容改回
注错前」这一点由提交序列本身承担，未在此机器复算。

fail-closed 约定：证据文件缺失、run 标识未回填、字段缺失、锚点未命中都计失败
并非零退出。未采集 CI 证据时本脚本必红，这正是「证据缺口」的机器可复算表述。
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_DIR = ROOT / "docs" / "acceptance-contracts" / "P3-7-v1" / "ci"

FIRMWARE_WORKFLOW = "MCU Firmware Build"
BUILD_JOB = "Build firmware (arm-none-eabi-gcc)"
STEP_NAME = "Run host tests (boot vectors, OTA host tests, P3-1 product regressions)"
# P3-6 实测该步骤序号为 10；本卡只改步骤名与步骤内命令、未新增步骤，序号应不变。
STEP_NUMBER = 10

# 采集后回填。留 None 即视为证据未采集（fail-closed，不是跳过）。
BASELINE_RUN = 33736951606          # 正例：接线提交，绿
TRIGGER_RUN = 33746544048           # 触发器反证 A：只改一条新增精确条目对应的脚本
TRIGGER_GLOB_RUN = 33746838579      # 触发器反证 B：只改 cmd12 脚本（验既有通配覆盖）
DEFECT_RUNS = {              # 四次注错，键为被打红的接线序号（0..3）
    0: 33742087214,          # cmd9  ota_ble_frame.h ACK_BEGIN 10u->11u
    1: 33743950837,          # cmd10 HAL_Bluetooth.cpp 移除活跃期 sink 守卫
    2: 33748460404,          # cmd11 HAL_USB.cpp 加 #if 0 反斜杠 include 阳性样本
    3: 33745505165,          # cmd12 ota_device_info.c model 首字符 'E'->'F'
}
RESTORE_RUNS = {             # 对应四次还原后的绿
    0: 33743337327,
    1: 33744219606,
    2: 33748868768,
    3: 33745844623,
}
PR_NUMBER = 19
HEAD_BRANCH = "ota/p3-7-host-test-wiring"

# 步骤内应被下发的完整命令序列（末四条为本卡接线）。
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
    "python3 tests/ota/p3_1_verify_contract_alignment.py",
    "python3 tests/ota/p3_1_verify_text_isolation.py",
    "python3 tests/ota/p3_1_verify_portability.py",
    "python3 tests/ota/test_ota_device_info.py",
)
# 新增四行之前的 8 条既有测试的结论标记。红运行里必须全部出现，
# 否则无法排除「红在既有测试」而非「红在本卡接线」。
PRECEDING_MARKERS = (
    "P1_1_FW_HEADER_VECTORS=PASS",
    "P1_1_BOOT_PROTOCOLS=PASS",
    "P1_3_STATE_MACHINE=PASS",
    "P2_1_STAGING=PASS",
    "P2_2_PACKAGE=PASS",
    "P2_3_VECTOR_PREFLIGHT=PASS",
    "P3_1_BLE_FRAME=PASS checks=39 failures=0",
    "P3_1_BLE_SESSION=PASS checks=105 failures=0",
)

# 四条接线各自的可观测形态。
#   script     : 步骤内的命令
#   pass_res   : 绿运行里每条模式必须恰好命中 1 次
#   any_re     : 该行是否被执行到（用于「更靠后的行必须零输出」）
#   fail_res   : 红运行里每条模式必须至少命中 1 次
#   target     : 该次反证冻结的注错目标文件（红/绿提交必须恰改这一个文件）
# 注意 cmd12 与前三条形态不同：`test_ota_device_info.py` 失败时不打印 `=FAIL`
# 汇总行，而是 C 用例输出 failures>0 并返回 1、Python 侧 check=True 抛出，
# `_ALL=PASS` 不再出现。故其判据按「failures 非零 + 存在 FAIL: 明细 +
# _ALL=PASS 缺席」构造，不能照抄前三条的 `=FAIL` 前缀写法。
WIRED = (
    {
        "script": "tests/ota/p3_1_verify_contract_alignment.py",
        "pass_res": (re.compile(r"^P3_1_CONTRACT_ALIGNMENT=PASS drift=0 checks=47$"),),
        "any_re": re.compile(r"^P3_1_CONTRACT_ALIGNMENT="),
        "fail_res": (re.compile(r"^P3_1_CONTRACT_ALIGNMENT=FAIL drift=[1-9]\d* checks=\d+$"),),
        "target": "Libraries/OTA/ota_ble_frame.h",
    },
    {
        "script": "tests/ota/p3_1_verify_text_isolation.py",
        "pass_res": (
            re.compile(
                r"^P3_1_TEXT_ISOLATION=PASS cases=3 transparent=0 trace_points=1 "
                r"sink_guard=True$"
            ),
        ),
        "any_re": re.compile(r"^P3_1_TEXT_ISOLATION="),
        "fail_res": (re.compile(r"^P3_1_TEXT_ISOLATION=FAIL .*sink_guard=False$"),),
        "target": "USER/HAL/HAL_Bluetooth.cpp",
    },
    {
        "script": "tests/ota/p3_1_verify_portability.py",
        # `scanned` 是随目录内容变化的信息字段（立卡基线 893、P3-2 落地后 895），
        # 用 \d+ 放行；其余为判据字段，逐字固定。
        "pass_res": (
            re.compile(
                r"^P3_1_PORTABILITY=PASS scanned=\d+ control_hits=1 live_hits=0 "
                r"new_src_hits=0$"
            ),
        ),
        "any_re": re.compile(r"^P3_1_PORTABILITY="),
        # 阳性对照必须同轮仍命中，否则「live_hits=1」可能来自扫描器整体失灵。
        "fail_res": (
            re.compile(r"^P3_1_PORTABILITY=FAIL scanned=\d+ control_hits=1 live_hits=[1-9]\d*"),
        ),
        "target": "USER/HAL/HAL_USB.cpp",
    },
    {
        "script": "tests/ota/test_ota_device_info.py",
        "pass_res": (
            re.compile(r"^P3_2_OTA_DEVICE_INFO checks=114 failures=0$"),
            re.compile(r"^P3_2_OTA_DEVICE_INFO_ALL=PASS$"),
        ),
        "any_re": re.compile(r"^P3_2_OTA_DEVICE_INFO"),
        "fail_res": (
            re.compile(r"^P3_2_OTA_DEVICE_INFO checks=\d+ failures=[1-9]\d*$"),
            re.compile(r"^FAIL: .+$"),
        ),
        "target": "Libraries/OTA/ota_device_info.c",
    },
)
WIRED_SCRIPTS = tuple(leg["script"] for leg in WIRED)
# 触发器反证 A 只能改这三条：它们对应本卡**新增**的精确 paths 条目。
TRIGGER_A_SCRIPTS = WIRED_SCRIPTS[:3]
# 触发器反证 B 固定为 cmd12：它由既有通配覆盖，未新增条目。
TRIGGER_B_SCRIPT = WIRED_SCRIPTS[3]
# 正例提交不得触碰任何产品红线目录。
PRODUCT_PREFIXES = ("Libraries/", "USER/", "boot/", "MDK-ARM_F435/")

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


def changed_files(run_id, label):
    """读取某 run 对应提交的改动文件清单。

    采集命令（每个需要绑定因果的 run 各一次）：
      gh api repos/:owner/:repo/commits/<headSha> \\
        --jq '[.files[] | {filename, sha}]' > changed-<run_id>.json
    """
    payload = load_json(f"changed-{run_id}.json")
    if payload is None:
        return None
    items = payload.get("files") if isinstance(payload, dict) else payload
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        failures.append(f"{label} run {run_id} 改动文件清单结构不符（应为对象数组）")
        return None
    names = sorted(str(item.get("filename")) for item in items)
    check(bool(names), f"{label} run {run_id} 改动文件清单为空（空集不得判通过）")
    return names


def step_conclusion(run, job_name, step_name):
    for job in run.get("jobs", []):
        if job.get("name") != job_name:
            continue
        for step in job.get("steps", []):
            if step.get("name") == step_name:
                return job.get("conclusion"), step.get("number"), step.get("conclusion")
    return None, None, None


def verify_run_metadata(run_id, expected_conclusion, expected_step, label):
    run = load_json(f"run-{run_id}.json")
    if run is None:
        return None
    check(str(run.get("databaseId")) == str(run_id), f"{label} run {run_id} databaseId 不符")
    check(run.get("workflowName") == FIRMWARE_WORKFLOW, f"{label} run {run_id} 工作流名不符")
    check(run.get("status") == "completed", f"{label} run {run_id} 未完成")
    check(
        run.get("conclusion") == expected_conclusion,
        f"{label} run {run_id} 结论不是 {expected_conclusion}：{run.get('conclusion')}",
    )
    head = run.get("headSha")
    check(
        isinstance(head, str) and re.fullmatch(r"[0-9a-f]{40}", head or "") is not None,
        f"{label} run {run_id} headSha 不是完整 40 位 SHA：{head}",
    )
    job_conclusion, number, conclusion = step_conclusion(run, BUILD_JOB, STEP_NAME)
    check(number == STEP_NUMBER, f"{label} run {run_id} 步骤序号不是 {STEP_NUMBER}：{number}")
    check(
        conclusion == expected_step,
        f"{label} run {run_id} 步骤结论不是 {expected_step}：{conclusion}",
    )
    check(
        job_conclusion == expected_conclusion,
        f"{label} run {run_id} 构建 job 结论不是 {expected_conclusion}",
    )
    print(
        f"{label} run={run_id} head={str(head)[:7]} run={run.get('conclusion')} "
        f"step{number}={conclusion}"
    )
    return run


def verify_echo(contents, run_id, label):
    start = None
    for index, line in enumerate(contents):
        if line.startswith("##[group]Run "):
            start = index
            break
    check(start is not None, f"{label} run {run_id} 日志缺少 ##[group]Run 分组")
    if start is None:
        return
    window = tuple(contents[start + 1: start + 1 + len(EXPECTED_ECHO)])
    check(
        window == EXPECTED_ECHO,
        f"{label} run {run_id} 命令回显与预期 {len(EXPECTED_ECHO)} 行不符：{list(window)}",
    )


def verify_bounding(contents, run_id, label):
    """红/绿运行共同的定界要求：前 8 条既有测试的标记必须照常出现。"""
    for marker in PRECEDING_MARKERS:
        check(
            any(line.startswith(marker) for line in contents),
            f"{label} run {run_id} 缺少前置标记 {marker}，无法排除红在既有测试或环境整体失败",
        )


def verify_green(run_id, label):
    contents, prefixes = load_step_log(f"step-{run_id}.txt")
    if contents is None:
        return
    check(
        prefixes == {(BUILD_JOB, STEP_NAME)},
        f"{label} run {run_id} 日志区段混入其他 job/step：{sorted(prefixes)}",
    )
    verify_echo(contents, run_id, label)
    verify_bounding(contents, run_id, label)
    for index, leg in enumerate(WIRED):
        for pattern in leg["pass_res"]:
            matched = [line for line in contents if pattern.match(line)]
            check(
                len(matched) == 1,
                f"{label} run {run_id} 第 {index + 1} 条接线结论标记缺失或重复："
                f"/{pattern.pattern}/ 命中 {len(matched)} 次",
            )
    check(
        not any("##[error]" in line for line in contents),
        f"{label} run {run_id} 绿运行日志内出现 ##[error]",
    )
    print(f"{label} run={run_id} log_lines={len(contents)} wired_markers={len(WIRED)}")


def verify_red(run_id, index, label):
    """index 为被注错打红的接线序号（0..3）。"""
    contents, prefixes = load_step_log(f"step-{run_id}.txt")
    if contents is None:
        return
    check(
        prefixes == {(BUILD_JOB, STEP_NAME)},
        f"{label} run {run_id} 日志区段混入其他 job/step：{sorted(prefixes)}",
    )
    verify_echo(contents, run_id, label)
    verify_bounding(contents, run_id, label)
    check(
        "##[error]Process completed with exit code 1." in contents,
        f"{label} run {run_id} 步骤未以退出码 1 结束",
    )
    # 红必须落在本卡新增的那一行：它之前的接线照常 PASS，
    # 它自身出现 FAIL 证据且不再有 PASS 标记，它之后的接线零输出（pipefail 短路）。
    for earlier in range(index):
        for pattern in WIRED[earlier]["pass_res"]:
            check(
                any(pattern.match(line) for line in contents),
                f"{label} run {run_id} 第 {earlier + 1} 条接线未照常通过，红点定界失败",
            )
    for pattern in WIRED[index]["fail_res"]:
        check(
            any(pattern.match(line) for line in contents),
            f"{label} run {run_id} 未出现第 {index + 1} 条接线的失败证据："
            f"/{pattern.pattern}/，缺陷未被该行捕获",
        )
    for pattern in WIRED[index]["pass_res"]:
        check(
            not any(pattern.match(line) for line in contents),
            f"{label} run {run_id} 第 {index + 1} 条接线仍报通过标记 "
            f"/{pattern.pattern}/，缺陷未被捕获",
        )
    for later in range(index + 1, len(WIRED)):
        check(
            not any(WIRED[later]["any_re"].match(line) for line in contents),
            f"{label} run {run_id} 第 {later + 1} 条接线仍有输出，"
            f"说明步骤未在首个失败处终止（fail-closed 语义不成立）",
        )
    print(f"{label} run={run_id} log_lines={len(contents)} red_at_wired={index + 1}")


def verify_injection_attribution(run_id, index, label):
    """红/绿 run 的提交必须恰改冻结的注错目标文件这一个，红因才可归属。"""
    names = changed_files(run_id, label)
    if names is None:
        return
    target = WIRED[index]["target"]
    check(
        names == [target],
        f"{label} run {run_id} 提交改动文件不是恰为注错目标 {target}：{names}",
    )


def verify_workflow_identity(run_id):
    """正例绿运行执行的 workflow 字节必须与最终落到 main 的一致。

    仅凭「某次 run 绿了」不足以证明门禁已生效：那次 run 可能跑的是与最终合并
    内容不同的 workflow。收口若采用 squash，提交可达性也不能承担这个证明。
    因此把该 run 的 headSha 处的 workflow 原文冻结进包，与工作树字节逐字节比。
    """
    run = load_json(f"run-{run_id}.json")
    if run is None:
        return
    head = run.get("headSha")
    if not isinstance(head, str) or not head:
        return
    frozen = CI_DIR / f"workflow-at-{head[:12]}.yml"
    if not frozen.is_file():
        failures.append(f"证据文件缺失：ci/{frozen.name}（正例 run 处的 workflow 原文）")
        return
    live = ROOT / ".github" / "workflows" / "firmware-build.yml"
    frozen_sha = hashlib.sha256(frozen.read_bytes()).hexdigest().upper()
    live_sha = hashlib.sha256(live.read_bytes()).hexdigest().upper()
    check(
        frozen_sha == live_sha,
        f"正例 run {run_id} 处的 workflow 与当前树不一致："
        f"冻结 {frozen_sha[:16]} vs 当前 {live_sha[:16]}，绿运行不能代表最终门禁",
    )
    print(f"workflow 同一性 run={run_id} head={head[:7]} sha256={live_sha[:16]}…")


def verify_baseline_scope(run_id):
    """正例提交只做接线，不得触碰产品红线目录。"""
    names = changed_files(run_id, "正例")
    if names is None:
        return
    check(
        ".github/workflows/firmware-build.yml" in names,
        f"正例 run {run_id} 提交未包含被改的 workflow：{names}",
    )
    intruders = [n for n in names if n.startswith(PRODUCT_PREFIXES)]
    check(not intruders, f"正例 run {run_id} 提交触碰了产品红线目录：{intruders}")


def verify_trigger(run_id, eligible, label):
    """触发器反证：只改被接入脚本自身的提交必须触发本工作流并执行到脚本。"""
    run = verify_run_metadata(run_id, "success", "success", label)
    if run is None:
        return
    names = changed_files(run_id, label)
    if names is None:
        return
    check(
        len(names) == 1 and names[0] in eligible,
        f"{label} run {run_id} 改动文件不是恰好一个 {list(eligible)} 中的脚本：{names}",
    )
    verify_green(run_id, label)


def main():
    if not CI_DIR.is_dir():
        print(
            f"FATAL: CI 证据目录缺失：{CI_DIR.relative_to(ROOT).as_posix()}",
            file=sys.stderr,
        )
        print("P3_7_CI_EVIDENCE=FAIL checks=0 failures=1 reason=ci_dir_missing")
        return 1

    legs = {
        "正例": BASELINE_RUN,
        "触发器反证A(新增精确条目)": TRIGGER_RUN,
        "触发器反证B(既有通配)": TRIGGER_GLOB_RUN,
        **{f"反证{i + 1}红": DEFECT_RUNS[i] for i in range(len(WIRED))},
        **{f"反证{i + 1}绿": RESTORE_RUNS[i] for i in range(len(WIRED))},
    }
    missing = [name for name, value in legs.items() if not value]
    check(not missing, f"以下 CI 运行标识未回填：{missing}")
    check(bool(PR_NUMBER), "PR 编号未回填")
    check(bool(HEAD_BRANCH), "特性分支名未回填")
    check(
        len(set(value for value in legs.values() if value)) == len(legs),
        f"CI 运行标识存在复用（同一 run 不得充当多条腿）：{legs}",
    )

    if BASELINE_RUN:
        verify_run_metadata(BASELINE_RUN, "success", "success", "正例")
        verify_green(BASELINE_RUN, "正例")
        verify_workflow_identity(BASELINE_RUN)
        verify_baseline_scope(BASELINE_RUN)
    if TRIGGER_RUN:
        verify_trigger(TRIGGER_RUN, TRIGGER_A_SCRIPTS, "触发器反证A(新增精确条目)")
    if TRIGGER_GLOB_RUN:
        verify_trigger(TRIGGER_GLOB_RUN, (TRIGGER_B_SCRIPT,), "触发器反证B(既有通配)")
    for index in range(len(WIRED)):
        if DEFECT_RUNS[index]:
            label = f"反证{index + 1}红"
            verify_run_metadata(DEFECT_RUNS[index], "failure", "failure", label)
            verify_red(DEFECT_RUNS[index], index, label)
            verify_injection_attribution(DEFECT_RUNS[index], index, label)
        if RESTORE_RUNS[index]:
            label = f"反证{index + 1}绿"
            verify_run_metadata(RESTORE_RUNS[index], "success", "success", label)
            verify_green(RESTORE_RUNS[index], label)
            verify_injection_attribution(RESTORE_RUNS[index], index, label)

    if PR_NUMBER:
        pull_request = load_json(f"pr-{PR_NUMBER}.json")
        if pull_request is not None:
            commits = [str(item.get("oid")) for item in pull_request.get("commits", [])]
            check(pull_request.get("baseRefName") == "main", "PR 基分支不是 main")
            check(
                pull_request.get("headRefName") == HEAD_BRANCH,
                f"PR 头分支不是 {HEAD_BRANCH}：{pull_request.get('headRefName')}",
            )
            check(bool(commits), "PR 提交清单为空（空集不得判通过）")
            print(f"pr={PR_NUMBER} commits={len(commits)}")

    print(f"=== 失败项 {len(failures)} / 核对项 {checks} ===")
    for item in failures:
        print(f"FAIL: {item}")
    status = "PASS" if not failures else "FAIL"
    print(f"P3_7_CI_EVIDENCE={status} checks={checks} failures={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
