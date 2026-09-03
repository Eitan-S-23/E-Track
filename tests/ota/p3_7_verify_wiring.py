#!/usr/bin/env python3
"""P3-7 独立验收：workflow 接线、触发器互镜、闭包与改动范围的静态核验。

只读仓库文本与 git 对象，不联网、不构建。回答派工书完成判据里可离线判定的部分：

  A 段 —— 目标步骤的命令序列、fail-closed 结构、步骤名与实际内容对齐；
  B 段 —— push / pull_request 两份 `paths` 同步扩条目、闭包（每条执行行都被
          触发器覆盖）与互镜（新增条目不覆盖未接入脚本）；
  C 段 —— 冻结红线：三条被接脚本零改动且仍是原路径、阳性对照存档未动、
          顶层 name 与 job name 字节未变、其余红线路径未被触碰；
  D 段 —— 改动范围逐条归类，以及字节卫生（混合 EOL 未被归一、无 BOM、
          看板列表项格式）。

「至少一次真实 CI 运行日志」不在本脚本范围内，由
`tests/ota/p3_7_verify_ci_evidence.py` 读取冻结的 run 元数据与步骤日志回答。

fail-closed 约定：
  * 任一断言失败即非零退出，不存在「没有报错就算过」的分支；
  * 凡以集合为主语的断言（红线未命中、无 fail-open 写法等）都先要求集合非空，
    空集不得当作通过 —— 这是 `p3_2_verify_scope.py` 在收口后静默转绿的教训。
"""

import fnmatch
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ".github/workflows/firmware-build.yml"
BOARD = "PLAN-OTA-EXEC.md"

TOP_NAME = "MCU Firmware Build"
JOB_NAME = "Build firmware (arm-none-eabi-gcc)"
OLD_STEP_NAME = "Test Boot fw_header validator vectors"
NEW_STEP_NAME = "Run host tests (boot vectors, OTA host tests, P3-1 product regressions)"

# 接线前该步骤内的 8 条命令（P3-6 收口后的 main 状态），顺序即步骤内顺序。
BASELINE_COMMANDS = (
    "python3 tests/boot/test_fw_header_vectors.py",
    "python3 tests/boot/test_boot_protocols.py",
    "python3 tests/boot/test_boot_state_machine.py",
    "python3 tests/ota/test_ota_staging.py",
    "python3 tests/ota/test_ota_package.py",
    "python3 tests/ota/test_ota_patch.py",
    "python3 tests/ota/test_ota_ble_frame.py",
    "python3 tests/ota/test_ota_ble_session.py",
)
# 本卡（派工书 v2）要求接入的四条产品测试/回归，即步骤内的 cmd9-cmd12。
WIRED_SCRIPTS = (
    "tests/ota/p3_1_verify_contract_alignment.py",
    "tests/ota/p3_1_verify_text_isolation.py",
    "tests/ota/p3_1_verify_portability.py",
    "tests/ota/test_ota_device_info.py",
)
# 只有前三条需要新增精确 paths 条目。第四条已被既有通配 `tests/ota/test_ota_*.py`
# 覆盖，再加精确条目属冗余，且会让「新增条目集合」多出一项而削弱互镜判据的定界。
ADDED_PATH_ENTRIES = WIRED_SCRIPTS[:3]
PRE_COVERED_SCRIPT = WIRED_SCRIPTS[3]
PRE_COVERING_GLOB = "tests/ota/test_ota_*.py"
# 立卡笔记 §3 裁定「不接入」的 5 个验收工具脚本，新增触发器条目不得覆盖它们。
NOT_WIRED_SCRIPTS = (
    "tests/ota/p3_1_verify_mutation.py",
    "tests/ota/p3_1_verify_production_binary.py",
    "tests/ota/p3_1_verify_rx_ring_budget.py",
    "tests/ota/p3_1_verify_artifacts.py",
    "tests/ota/p3_1_verify_command_fidelity.py",
)
POSITIVE_CONTROL = "Libraries/USB_MSC/msc_diskio.c.old"

# 本卡交付的基线 main（PR #19 的 base）。交付比对一律相对它，而非相对 HEAD：
# 相对 HEAD 的写法只在「交付尚未提交」的那一瞬成立，提交后即自毁，属轮次作用域
# 钉子；相对固定基线则是不变量，提交前后都成立。
DELIVERY_BASE = "2d8ff7e52d4c575a4d109b1477a79a7c1493d81b"

# 立卡笔记 §3 的锚定提交与当时实测的扫描文件数；两者用于把 portability 的
# `scanned` 增量逐文件解释清楚，而不是笼统写「目录自然增长」。
CARD_BASELINE_REV = "dd0a9952ca2edde8c236a4b1cc57a3ec8879ca0d"
CARD_BASELINE_SCANNED = 893
SCANNED_DELTA_EXPECTED = (
    "Libraries/OTA/ota_device_info.c",
    "Libraries/OTA/ota_device_info.h",
)

FAIL_OPEN = (
    r"\|\|\s*true\b",
    r"\|\|\s*:\s*$",
    r"continue-on-error:\s*true",
    r"set\s+\+e",
    r"if:\s*always\(\)",
    r"^\s*exit\s+0\s*$",
)

# 本卡范围外的红线：改到即越界。`.github/workflows/firmware-build.yml` 是本卡
# 唯一允许改的 workflow，故按文件而非目录列举另一份。
RED_LINE_PATHSPECS = (
    r"^boot/",
    r"^Libraries/OTA/",
    r"^USER/",
    r"^PLAN-OTA\.md$",
    r"^docs/ota-binary-contracts\.md$",
    r"^docs/ota-cross-system-contracts\.md$",
    r"^docs/acceptance-execution-contract\.md$",
    r"^Tools/etu_pack\.py$",
    r"^Tools/acceptance/",
    r"^Tools/provenance/",
    r"^\.github/workflows/acceptance-governance\.yml$",
    r"^tests/ota-vectors/",
    r"^tests/ota/p3_1_verify_",
    r"^Libraries/USB_MSC/",
)

TIER_P3_7_CARD = (
    r"^\.github/workflows/firmware-build\.yml$",
    r"^docs/ota-exec-notes/P3-7-(research-wiring|wiring-evidence)\.md$",
    # 实现方 v2 用于「按 CI 同序跑全部 12 条」的本地预演驱动。
    r"^\.claude/p3_7_run_ci_sequence\.py$",
)
TIER_ACCEPTANCE = (
    r"^tests/ota/p3_7_verify_[a-z_]+\.py$",
    r"^docs/acceptance-contracts/P3-7-v1\.contract\.json$",
    r"^docs/acceptance-contracts/P3-7-v1/",
    r"^docs/ota-exec-notes/P3-7-acceptance-.*\.md$",
    r"^\.claude/verification-report-p3-7\.md$",
    r"^\.claude/write_p3_7_acceptance_board\.py$",
    # 派工书 v2：看板 §0 规则 11 要求派工前由非实现会话冻结，故归验收方。
    r"^docs/ota-prompts/prompt-P3-7-implementation\.md$",
    # 为本卡两个验收核验器补 `-text` 护栏，防 autocrlf 打红冻结指纹。
    r"^\.gitattributes$",
)
TIER_SHARED = (r"^PLAN-OTA-EXEC\.md$",)

PREEXISTING_UNTRACKED = (
    ".cache-cmake-time-test.cmake",
    ".claude/cc_recover_s4.js",
    ".claude/ccprobe_hash.js",
    ".claude/ccprobe_plan.js",
    ".claude/write_p3_2_acceptance_board.py",
    ".claude/write_r5_phase0_board.py",
    ".claude/write_r5_ruling_board.py",
)

failures = []
checks = 0


def ck(cond, label, got=None, want=None):
    global checks
    checks += 1
    if cond:
        print(f"  ok   {label}" + (f" = {got!r}" if got is not None else ""))
    else:
        detail = ""
        if got is not None or want is not None:
            detail = f": got={got!r} want={want!r}"
        print(f"  FAIL {label}{detail}")
        failures.append(label)


def git(*args):
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args], capture_output=True, check=False
    )
    if result.returncode != 0:
        raise SystemExit(
            f"FATAL: git {' '.join(args)} 失败 rc={result.returncode}: "
            f"{result.stderr.decode('utf-8', 'replace')[:200]}"
        )
    return result.stdout.decode("utf-8")


def git_show_bytes(revision, repo_path):
    result = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{revision}:{repo_path}"],
        capture_output=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def lines_of(text):
    return [line.rstrip("\r") for line in text.split("\n")]


def eol_stats(blob):
    crlf = blob.count(b"\r\n")
    return crlf, blob.count(b"\n") - crlf


def extract_step(lines, step_name):
    """按缩进抽取指定 name 的步骤块与其 run 脚本行。"""
    marker = f"- name: {step_name}"
    start = indent = None
    for index, line in enumerate(lines):
        if line.strip() == marker:
            start, indent = index, len(line) - len(line.lstrip(" "))
            break
    if start is None:
        return None, None
    block = [lines[start]]
    for line in lines[start + 1:]:
        if not line.strip():
            block.append(line)
            continue
        current = len(line) - len(line.lstrip(" "))
        if current <= indent and line.strip().startswith("- "):
            break
        if current <= indent - 2:
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
    return block, run_lines


def parse_paths_lists(lines):
    """抽取 on.push.paths 与 on.pull_request.paths 两份列表（保持顺序）。

    只认 `on:` → 事件 → `paths:` → `- "..."` 这一种既有写法；结构变形时返回
    None 而不是猜测，交由调用方计失败。
    """
    result = {}
    in_on = False
    event = None
    in_paths = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent == 0:
            in_on = stripped == "on:"
            event = None
            in_paths = False
            continue
        if not in_on:
            continue
        if indent == 2 and stripped.endswith(":"):
            event = stripped[:-1]
            in_paths = False
            continue
        if indent == 4 and stripped == "paths:":
            in_paths = True
            if event is not None:
                result.setdefault(event, [])
            continue
        if indent == 4 and stripped.endswith(":"):
            in_paths = False
            continue
        if in_paths and stripped.startswith("- ") and event is not None:
            result[event].append(stripped[2:].strip().strip('"'))
            continue
        if in_paths and indent <= 4:
            in_paths = False
    return result


def glob_match(pattern, path):
    """GitHub paths 的 glob 语义：`**` 跨目录，`*` 不跨 `/`。"""
    regex = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if pattern.startswith("**", index):
            regex.append(".*")
            index += 2
            continue
        if char == "*":
            regex.append("[^/]*")
        elif char == "?":
            regex.append("[^/]")
        else:
            regex.append(re.escape(char))
        index += 1
    return re.fullmatch("".join(regex), path) is not None


def main():
    print("=== P3-7 接线静态核验 ===")
    head_workflow = git_show_bytes(DELIVERY_BASE, WORKFLOW)
    if head_workflow is None:
        raise SystemExit(f"FATAL: 无法读取 {DELIVERY_BASE[:7]}:{WORKFLOW}")
    work_path = ROOT / WORKFLOW
    if not work_path.is_file():
        raise SystemExit(f"FATAL: 工作树缺少 {WORKFLOW}")
    raw = work_path.read_bytes()
    text = raw.decode("utf-8")
    lines = lines_of(text)
    head_lines = lines_of(head_workflow.decode("utf-8"))
    print(
        f"workflow size={len(raw)} sha256={hashlib.sha256(raw).hexdigest().upper()[:16]} "
        f"head_size={len(head_workflow)}"
    )

    # ---------------- A 段：步骤结构与 fail-closed ----------------
    print("== A. 目标步骤与 fail-closed 结构 ==")
    ck(text.count(f"name: {TOP_NAME}") == 1, "顶层 name 保持 MCU Firmware Build")
    ck(
        git_show_bytes(DELIVERY_BASE, WORKFLOW).decode("utf-8").count(f"name: {TOP_NAME}") == 1
        and [l for l in lines if l.strip() == f"name: {TOP_NAME}"]
        == [l for l in head_lines if l.strip() == f"name: {TOP_NAME}"],
        "顶层 name 行相对基线 main 逐字节未变",
    )
    ck(
        [l for l in lines if l.strip() == f"name: {JOB_NAME}"]
        == [l for l in head_lines if l.strip() == f"name: {JOB_NAME}"]
        and any(l.strip() == f"name: {JOB_NAME}" for l in lines),
        "jobs.build.name 行相对基线 main 逐字节未变且存在",
    )
    ck(OLD_STEP_NAME not in text, "旧步骤名已不存在（名称与实际内容对齐）")

    block, run_lines = extract_step(lines, NEW_STEP_NAME)
    ck(block is not None, f"存在步骤 `{NEW_STEP_NAME}`")
    ck(bool(run_lines), "该步骤存在非空 run 脚本块", len(run_lines or []))
    if not run_lines:
        return report()

    expected = ["set -euo pipefail"] + list(BASELINE_COMMANDS) + [
        f"python3 {s}" for s in WIRED_SCRIPTS
    ]
    ck(run_lines == expected, "步骤命令序列精确等于 8 条既有 + 4 条接线", run_lines, expected)
    ck(run_lines[0] == "set -euo pipefail", "步骤首行是 set -euo pipefail")
    guard = run_lines.index("set -euo pipefail")
    for script in WIRED_SCRIPTS:
        command = f"python3 {script}"
        present = command in run_lines
        ck(present, f"接线命令存在：{command}")
        ck(
            present and run_lines.index(command) > guard,
            f"接线命令落在 set -euo pipefail 之后：{command}",
        )
        ck(
            present and run_lines[run_lines.index(command)] == command,
            f"接线命令未被额外子句包裹：{command}",
        )
    block_text = "\n".join(block)
    ck("continue-on-error" not in block_text, "目标步骤无 continue-on-error")
    ck(not re.search(r"^\s*if:", block_text, re.MULTILINE), "目标步骤无 if: 条件")

    body_lines = [l for l in lines if not l.strip().startswith("#")]
    ck(len(body_lines) > 100, "workflow 非注释行集合非空（空集守卫）", len(body_lines))
    for pattern in FAIL_OPEN:
        hits = [i + 1 for i, l in enumerate(lines) if not l.strip().startswith("#") and re.search(pattern, l)]
        ck(not hits, f"全文件无 fail-open 写法 /{pattern}/", hits, [])

    # ---------------- B 段：触发器互镜与闭包 ----------------
    print("== B. 触发器同步、闭包与互镜 ==")
    current = parse_paths_lists(lines)
    base = parse_paths_lists(head_lines)
    ck(set(current) >= {"push", "pull_request"}, "解析出 push / pull_request 两份触发器", sorted(current))
    push = current.get("push") or []
    pull = current.get("pull_request") or []
    ck(bool(push) and bool(pull), "两份 paths 列表均非空（空集守卫）", (len(push), len(pull)))
    ck(push == pull, "两份 paths 逐项相等（同序同项）", push, pull)
    for script in ADDED_PATH_ENTRIES:
        ck(script in push, f"push.paths 含精确条目：{script}")
        ck(script in pull, f"pull_request.paths 含精确条目：{script}")
    # 第四条接线走既有通配覆盖，不得也不必新增精确条目。
    ck(
        PRE_COVERED_SCRIPT not in push and PRE_COVERED_SCRIPT not in pull,
        f"未为已被通配覆盖的脚本新增冗余精确条目：{PRE_COVERED_SCRIPT}",
    )
    ck(
        PRE_COVERING_GLOB in push and PRE_COVERING_GLOB in pull,
        f"覆盖它的既有通配仍在两份 paths 内：{PRE_COVERING_GLOB}",
    )
    ck(
        glob_match(PRE_COVERING_GLOB, PRE_COVERED_SCRIPT),
        f"通配确实覆盖该脚本（覆盖关系实算，非声明）：{PRE_COVERING_GLOB} -> {PRE_COVERED_SCRIPT}",
    )

    base_push = base.get("push") or []
    base_pull = base.get("pull_request") or []
    ck(bool(base_push) and bool(base_pull), "基线 main 两份 paths 解析非空（空集守卫）", (len(base_push), len(base_pull)))
    ck(
        [p for p in base_push if p not in push] == [],
        "push.paths 未删除任何既有条目",
        [p for p in base_push if p not in push],
        [],
    )
    ck(
        [p for p in base_pull if p not in pull] == [],
        "pull_request.paths 未删除任何既有条目",
        [p for p in base_pull if p not in pull],
        [],
    )
    added_push = [p for p in push if p not in base_push]
    added_pull = [p for p in pull if p not in base_pull]
    ck(added_push == list(ADDED_PATH_ENTRIES), "push.paths 新增恰为三条脚本", added_push, list(ADDED_PATH_ENTRIES))
    ck(added_pull == list(ADDED_PATH_ENTRIES), "pull_request.paths 新增恰为三条脚本", added_pull, list(ADDED_PATH_ENTRIES))

    # 闭包：步骤内每条执行行的目标路径都必须被 paths 覆盖。
    executed = [l.split()[1] for l in run_lines if l.startswith("python3 ")]
    ck(len(executed) == 12, "步骤内 python3 执行行计数", len(executed), 12)
    ck(bool(executed), "执行行集合非空（空集守卫）")
    for target in executed:
        ck(
            any(glob_match(pattern, target) for pattern in push),
            f"闭包：执行行被 paths 覆盖 {target}",
        )
        ck(
            (ROOT / target).is_file(),
            f"执行行指向的文件真实存在 {target}",
        )
    # 互镜：**实际观测到的**新增条目不得覆盖任何不接入脚本。这里必须用 added_*
    # 而不是 WIRED_SCRIPTS 常量——用常量当模式时断言恒真（字面文件名永远匹配不到
    # 别的脚本），是典型的空转绿。
    added_union = list(dict.fromkeys(added_push + added_pull))
    ck(bool(added_union), "新增触发器条目集合非空（空集守卫）", added_union)
    for script in NOT_WIRED_SCRIPTS:
        covered = [pattern for pattern in added_union if glob_match(pattern, script)]
        ck(
            not covered,
            f"新增条目未覆盖不接入脚本 {script}",
            covered,
            [],
        )
        ck(
            script not in executed,
            f"不接入脚本未被写进执行行 {script}",
        )
    # 互镜断言自身的阳性对照：通配模式必须能被上面的写法判红，否则该段无鉴别力。
    ck(
        glob_match("tests/ota/p3_1_verify_*.py", NOT_WIRED_SCRIPTS[0]),
        "互镜判据阳性对照：通配模式确实会命中不接入脚本",
    )

    # ---------------- C 段：冻结红线 ----------------
    print("== C. 冻结红线 ==")
    tracked = sorted(
        set(
            [l for l in git("diff", "--name-only", DELIVERY_BASE).splitlines() if l]
            + [l for l in git("diff", "--cached", "--name-only").splitlines() if l]
        )
    )
    untracked = sorted(l for l in git("ls-files", "-o", "--exclude-standard").splitlines() if l)
    changed = tracked + untracked
    ck(len(changed) >= 4, "本轮改动集合非空且下限成立（空集守卫）", len(changed))
    for script in WIRED_SCRIPTS + NOT_WIRED_SCRIPTS + (POSITIVE_CONTROL,):
        ck(script not in tracked, f"零改动：{script}")
        listed = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", script],
            capture_output=True,
            check=False,
        )
        ck(listed.returncode == 0, f"仍是原路径的跟踪文件（未改名/移动）：{script}")
    for pattern in RED_LINE_PATHSPECS:
        hits = [p for p in changed if re.search(pattern, p)]
        ck(not hits, f"红线未被改动 /{pattern}/", hits, [])

    # ---------------- D 段：改动范围与字节卫生 ----------------
    print("== D. 改动范围与字节卫生 ==")
    buckets = {"P3-7": [], "验收": [], "共有": [], "既有": [], "未归类": []}
    for path in changed:
        if path in PREEXISTING_UNTRACKED:
            buckets["既有"].append(path)
        elif any(re.search(p, path) for p in TIER_P3_7_CARD):
            buckets["P3-7"].append(path)
        elif any(re.search(p, path) for p in TIER_ACCEPTANCE):
            buckets["验收"].append(path)
        elif any(re.search(p, path) for p in TIER_SHARED):
            buckets["共有"].append(path)
        else:
            buckets["未归类"].append(path)
    for name, items in buckets.items():
        print(f"  [{name}] {len(items)} 项: {items}")
    ck(not buckets["未归类"], "无法归类的改动为空", buckets["未归类"], [])
    ck(
        sorted(buckets["P3-7"])
        == [
            ".claude/p3_7_run_ci_sequence.py",
            ".github/workflows/firmware-build.yml",
            "docs/ota-exec-notes/P3-7-research-wiring.md",
            "docs/ota-exec-notes/P3-7-wiring-evidence.md",
        ],
        "P3-7 卡内改动恰为 workflow + 两份笔记 + 预演驱动",
        sorted(buckets["P3-7"]),
    )
    ck(buckets["共有"] == [BOARD], "共有改动恰为看板", buckets["共有"], [BOARD])
    ck(
        sorted(buckets["既有"]) == sorted(PREEXISTING_UNTRACKED),
        "既有未跟踪残留清单全等",
        sorted(buckets["既有"]),
        sorted(PREEXISTING_UNTRACKED),
    )

    head_crlf, head_lf = eol_stats(head_workflow)
    cur_crlf, cur_lf = eol_stats(raw)
    ck(cur_crlf == head_crlf, "workflow CRLF 计数未变（未被 EOL 归一）", cur_crlf, head_crlf)
    ck(cur_lf == head_lf + 10, "workflow 裸 LF 计数恰增 10（10 条新增行）", cur_lf, head_lf + 10)
    numstat = [l.split("\t") for l in git("diff", "--numstat", DELIVERY_BASE, "--", WORKFLOW).splitlines() if l]
    ck(numstat and numstat[0][:2] == ["11", "1"], "workflow diff 为 11 增 1 删", numstat, [["11", "1"]])
    ws = [l.split("\t") for l in git("diff", "--numstat", "-w", DELIVERY_BASE, "--", WORKFLOW).splitlines() if l]
    ck(ws and ws[0][:2] == ["11", "1"], "workflow -w diff 同为 11/1（无仅空白差异对）", ws)

    head_board = git_show_bytes(DELIVERY_BASE, BOARD)
    board_raw = (ROOT / BOARD).read_bytes()
    b_crlf, b_lf = eol_stats(board_raw)
    h_crlf, h_lf = eol_stats(head_board)
    # 以下三条是**轮次作用域**的溯源钉子（不是不变量）：它们钉的是「本卡在看板上留下
    # 的改动恰为这些，没有夹带」。构成 = 实现批次（状态行、证据行、§10 两行）+ 验收
    # 回写批次（状态行、验收行、证据行、新增验收发现行、§1 阶段总表 P3 行、§9 登记 1 行、
    # §10 一行）。看板混合行尾：§9 登记表为裸 LF，其余为 CRLF。
    ck(b_lf == h_lf + 1, "看板裸 LF 计数恰增 1（§9 登记表追加 1 行）", b_lf, h_lf + 1)
    ck(
        b_crlf == h_crlf + 4,
        "看板 CRLF 计数恰增 4（§10 追加 3 行 + 卡内新增验收发现 1 行）",
        b_crlf,
        h_crlf + 4,
    )
    board_numstat = [l.split("\t") for l in git("diff", "--numstat", DELIVERY_BASE, "--", BOARD).splitlines() if l]
    ck(board_numstat and board_numstat[0][:2] == ["9", "4"], "看板 diff 为 9 增 4 删", board_numstat)
    board_text = board_raw.decode("utf-8")
    # 哈希判据：长度 >= 7 的十六进制串，且同时含十六进制字母与数字。纯十进制串
    # （日期标识 20260903、Actions run 号）不是哈希，不在禁止范围内。
    card_text = board_text.split("#### P3-7")[1].split("\n---")[0]
    hashish = [
        token
        for token in re.findall(r"\b[0-9a-fA-F]{7,}\b", card_text)
        if re.search(r"[a-fA-F]", token) and re.search(r"[0-9]", token)
    ]
    ck(not hashish, "P3-7 卡内未出现任何哈希/commit SHA", hashish, [])
    session_log = [
        l.rstrip("\r")
        for l in board_text.split("## 10.")[-1].split("\n")
        if re.match(r"^-?\s*2026-", l.strip()) or l.strip().startswith("2026-")
    ]
    ck(bool(session_log), "§10 会话日志行集合非空（空集守卫）", len(session_log))
    bad_prefix = [l[:32] for l in session_log if not l.startswith("- ")]
    ck(not bad_prefix, "§10 每条日志行都以 Markdown 列表标记 `- ` 开头", bad_prefix, [])

    for note in (
        "docs/ota-exec-notes/P3-7-research-wiring.md",
        "docs/ota-exec-notes/P3-7-wiring-evidence.md",
    ):
        path = ROOT / note
        ck(path.is_file(), f"证据笔记存在：{note}")
        if path.is_file():
            blob = path.read_bytes()
            ck(not blob.startswith(b"\xef\xbb\xbf"), f"UTF-8 无 BOM：{note}")
            ck(len(blob) > 1000, f"笔记非空且有实质内容：{note}", len(blob))

    # ---------------- E 段：被接脚本实跑与计数对账 ----------------
    print("== E. 被接四脚本实跑与计数对账 ==")
    markers = {}
    outputs = {}
    for script in WIRED_SCRIPTS:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", script],
            capture_output=True,
            check=False,
            cwd=str(ROOT),
        )
        out = result.stdout.decode("utf-8", "replace")
        outputs[script] = out
        ck(result.returncode == 0, f"实跑退出码 0：{script}", result.returncode, 0)
        marker = [l.strip() for l in out.splitlines() if re.match(r"^P3_[0-9]_[A-Z_0-9]+=", l.strip())]
        ck(len(marker) == 1, f"实跑输出恰含一条结论标记：{script}", marker)
        if marker:
            markers[script] = marker[0]
            print(f"       {marker[0]}")
    for script, expected in {
        WIRED_SCRIPTS[0]: "P3_1_CONTRACT_ALIGNMENT=PASS drift=0 checks=47",
        WIRED_SCRIPTS[1]: (
            "P3_1_TEXT_ISOLATION=PASS cases=3 transparent=0 trace_points=1 sink_guard=True"
        ),
        WIRED_SCRIPTS[3]: "P3_2_OTA_DEVICE_INFO_ALL=PASS",
    }.items():
        ck(markers.get(script) == expected, f"结论标记逐字符等于基线：{script}", markers.get(script), expected)
    # portability 的 scanned 是随目录内容变化的信息字段，判据字段是后三项。
    port = markers.get(WIRED_SCRIPTS[2], "")
    fields = dict(
        item.split("=", 1) for item in port.split()[1:] if "=" in item
    ) if port else {}
    ck(port.startswith("P3_1_PORTABILITY=PASS"), "portability 结论为 PASS", port)
    ck(fields.get("control_hits") == "1", "阳性对照仍命中 1 处（对照非空守卫）", fields.get("control_hits"), "1")
    ck(fields.get("live_hits") == "0", "在编手写源零反斜杠 include", fields.get("live_hits"), "0")
    ck(fields.get("new_src_hits") == "0", "P3-1 新源零命中", fields.get("new_src_hits"), "0")

    # cmd12 的汇总行是判据字段（checks/failures 都被 P3-2 冻结），单独逐字符核对。
    ck(
        "P3_2_OTA_DEVICE_INFO checks=114 failures=0"
        in [l.strip() for l in outputs.get(WIRED_SCRIPTS[3], "").splitlines()],
        "cmd12 汇总行逐字符等于 P3-2 基线",
        [l.strip() for l in outputs.get(WIRED_SCRIPTS[3], "").splitlines() if "DEVICE_INFO" in l],
        "P3_2_OTA_DEVICE_INFO checks=114 failures=0",
    )

    # scanned 对账：独立按脚本自身的筛选规则重算，防止脚本自报数字被伪造；
    # 再把相对立卡笔记 §3 基线（893 @ dd0a995）的增量逐文件解释清楚。
    scan_dirs = ("Libraries", "USER", "MDK-ARM_F435/Platform")
    exts = {".c", ".cpp", ".h", ".hpp", ".cc", ".old"}

    def keep(rel):
        parts = Path(rel).parts
        return (
            rel.startswith(scan_dirs)
            and Path(rel).suffix.lower() in exts
            and not any(p.startswith("build") or p == "vendor" for p in parts)
        )

    worktree_set = set()
    for name in scan_dirs:
        for path in (ROOT / name).rglob("*"):
            if path.is_file():
                rel = path.relative_to(ROOT).as_posix()
                if keep(rel):
                    worktree_set.add(rel)
    ck(bool(worktree_set), "重算扫描集合非空（空集守卫）", len(worktree_set))
    ck(
        fields.get("scanned") == str(len(worktree_set)),
        "脚本自报 scanned 与独立重算一致",
        fields.get("scanned"),
        str(len(worktree_set)),
    )
    base_set = {
        line
        for line in git("ls-tree", "-r", "--name-only", CARD_BASELINE_REV).splitlines()
        if line and keep(line)
    }
    ck(len(base_set) == CARD_BASELINE_SCANNED, "立卡基线扫描数复现", len(base_set), CARD_BASELINE_SCANNED)
    ck(
        sorted(worktree_set - base_set) == list(SCANNED_DELTA_EXPECTED),
        "scanned 增量被逐文件解释（P3-2 落地新增的两个源）",
        sorted(worktree_set - base_set),
        list(SCANNED_DELTA_EXPECTED),
    )
    ck(not (base_set - worktree_set), "立卡基线内文件无一消失", sorted(base_set - worktree_set), [])

    governance = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", "-m", "unittest", "tests.ota.test_acceptance_bundle"],
        capture_output=True,
        check=False,
        cwd=str(ROOT),
    )
    gov_out = governance.stderr.decode("utf-8", "replace")
    ck(governance.returncode == 0, "治理自测退出码 0", governance.returncode, 0)
    ran = re.search(r"Ran (\d+) tests", gov_out)
    ck(bool(ran) and int(ran.group(1)) == 65, "治理自测用例数", ran.group(1) if ran else None, "65")
    ck("OK" in gov_out.splitlines()[-1] if gov_out.strip() else False, "治理自测末行为 OK")

    return report()


def report():
    print(f"=== 失败项 {len(failures)} / 核对项 {checks} ===")
    for item in failures:
        print(f"FAIL: {item}")
    status = "PASS" if not failures else "FAIL"
    print(f"P3_7_WIRING={status} checks={checks} failures={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
