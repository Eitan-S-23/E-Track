"""`run_all.py` 分类与汇总逻辑的 fail-closed 自检（四个负例 + 一个正例）。

**为什么需要它**：2026-08-16 定向复核复现了一个实际误判 —— 把探针 runner 路径
改成不存在的脚本后，Python 因"文件不存在"返回 2，旧汇总器只凭 `rc == 2` 判定，
输出 `[ENV_BLOCKED] missing_runner` 并以 `rc=2` 收场。那实际是 harness 故障，
不是工具链缺失；混合出现真实失败与工具链缺失时，旧逻辑还会用 `rc=2` 掩盖失败。

本自检把裁定要求的四个负例冻结成可执行断言，任何偏离即 `rc=1`：

| 编号 | 负例 | 期望标记 | 期望整体退出码 |
| --- | --- | --- | --- |
| N1 | 探针脚本缺失 | `HARNESS_FAIL` | 1 |
| N2 | 伪 `rc=2`（退出码 2 但无规范化标记，含旧格式输出） | `HARNESS_FAIL` | 1 |
| N3 | 真实环境阻塞 + harness 失败混合 | 两者并存 | 1（失败优先） |
| N4 | 纯环境阻塞（`require_tools` 签发标记） | `ENV_BLOCKED` | 2 |
| P1 | 全部通过（正例基线） | `PASS` | 0 |

P1 不可省：没有正例时，把 `classify()` 写成恒返回 `HARNESS_FAIL` 也能让四个
负例全过。

用法：`python tests/ota/spec-probes/p2-6/selftest/classification_selftest.py`
（`run_all.py` 会在跑正式探针之前自动以前置门禁方式调用本脚本）。
"""
import contextlib
import io
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_all  # noqa: E402
from _probe_env import ENV_BLOCKED_LINE_PREFIX, out_dir  # noqa: E402

PASS = run_all.MARK_PASS
ENV = run_all.MARK_ENV_BLOCKED
FAIL = run_all.MARK_HARNESS_FAIL

OUT = out_dir("selftest")
# 只认 `run_probes()` 的逐项行（必带 `rc=` 与 `日志:`）。若只匹配 `[标记]` 前缀，
# 汇总器自己的诊断行（例如条目数门禁的 `[HARNESS_FAIL] 探针条目数 ...`）会被
# 误当成"某个探针被执行过"，让"未执行任何探针"这条断言失去鉴别力。
MARK_LINE_RE = re.compile(
    r"^\[(PASS|ENV_BLOCKED|HARNESS_FAIL)\] (\S+)\s+rc=(\S+)\s+日志: "
)

# 假探针相对 `run_all.py` 所在目录的路径（`run_probe` 以该目录为基准解析）。
REL = "selftest/"
MISSING = REL + "fake_missing_probe_does_not_exist.py"   # 故意不入库
SPOOFED = REL + "fake_spoofed_env.py"
HARNESS = REL + "fake_harness_fail.py"
BLOCKED = REL + "fake_env_blocked.py"
OK = REL + "fake_pass.py"

# 端到端场景：(编号, 说明, probes, 期望标记序列, 期望退出码)
SCENARIOS = [
    ("N1", "探针脚本缺失必须是 harness 失败，不是环境阻塞",
     [("missing_runner", MISSING, "复现裁定给出的 missing_runner 负例")],
     [FAIL], 1),
    ("N2", "退出码 2 但无规范化标记（含旧格式输出）必须是 harness 失败",
     [("spoofed_env", SPOOFED, "伪 rc=2 不得冒充 ENV_BLOCKED")],
     [FAIL], 1),
    ("N3", "真实环境阻塞与 harness 失败混合时，失败优先，退出码必须是 1",
     [("real_blocked", BLOCKED, "真实 ENV_BLOCKED"),
      ("real_failure", HARNESS, "真实 harness 失败")],
     [ENV, FAIL], 1),
    ("N4", "纯环境阻塞（无任何失败）才允许退出码 2",
     [("ok", OK, "正常通过"),
      ("real_blocked", BLOCKED, "真实 ENV_BLOCKED")],
     [PASS, ENV], 2),
    ("P1", "全部通过必须退出码 0（否则分类可能恒判失败）",
     [("ok1", OK, "正常通过"), ("ok2", OK, "正常通过")],
     [PASS, PASS], 0),
]

# `classify()` 的纯函数判据：输入 (退出码, 输出) -> 期望标记。
REAL_MARK_LINE = f"{ENV_BLOCKED_LINE_PREFIX}工具链缺失: p2-6-tool-that-must-not-exist"
CLASSIFY_CASES = [
    ("退出码 0 即通过", 0, "", PASS),
    ("退出码 2 + 规范化标记 = 真实环境阻塞", 2, REAL_MARK_LINE, ENV),
    ("退出码 2 + 空输出", 2, "", FAIL),
    ("退出码 2 + 正文中间出现 ENV_BLOCKED 一词", 2,
     "stage said ENV_BLOCKED here", FAIL),
    ("退出码 2 + 旧格式（无标记）", 2,
     "[ENV_BLOCKED] 工具链缺失: arm-none-eabi-gcc", FAIL),
    ("标记行但退出码不是 2", 1, REAL_MARK_LINE, FAIL),
    ("被信号杀死的负退出码", -11, "", FAIL),
    ("普通断言失败", 1, "基线不再成立", FAIL),
]

# `aggregate()` 的优先级判据：标记序列 -> 期望退出码。
AGGREGATE_CASES = [
    ("空序列不得视为通过", [], 1),
    ("全通过", [PASS, PASS], 0),
    ("纯环境阻塞", [PASS, ENV], 2),
    ("失败优先于环境阻塞", [ENV, FAIL], 1),
    ("顺序无关", [FAIL, ENV], 1),
    ("纯失败", [FAIL], 1),
]


def parse_marks(text: str):
    """从 `main()` 的输出里提取汇总段之前的逐项标记，顺序与探针顺序一致。"""
    head = text.split("=== 汇总 ===")[0]
    return [
        match.group(1)
        for match in (MARK_LINE_RE.match(line) for line in head.splitlines())
        if match
    ]


def check_scenarios(failures):
    for tag, desc, probes, want_marks, want_rc in SCENARIOS:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = run_all.main(probes=probes, out_root=OUT, run_selftest=False)
        text = buffer.getvalue()
        got_marks = parse_marks(text)
        ok = rc == want_rc and got_marks == want_marks
        print(f"[{'PASS' if ok else 'FAIL'}] {tag} rc={rc}（期望 {want_rc}）"
              f" 标记={got_marks}（期望 {want_marks}）  {desc}")
        if not ok:
            failures.append(f"{tag}: rc={rc} 期望 {want_rc}；"
                            f"标记 {got_marks} 期望 {want_marks}")
            for line in text.splitlines():
                print("        | " + line)


def check_classify(failures):
    for desc, rc, output, want in CLASSIFY_CASES:
        got = run_all.classify(rc, output)
        ok = got == want
        print(f"[{'PASS' if ok else 'FAIL'}] classify(rc={rc}) = {got}"
              f"（期望 {want}）  {desc}")
        if not ok:
            failures.append(f"classify(rc={rc}, {desc}) = {got} 期望 {want}")


def check_aggregate(failures):
    for desc, marks, want in AGGREGATE_CASES:
        got = run_all.aggregate(marks)
        ok = got == want
        print(f"[{'PASS' if ok else 'FAIL'}] aggregate({marks}) = {got}"
              f"（期望 {want}）  {desc}")
        if not ok:
            failures.append(f"aggregate({marks}) = {got} 期望 {want}")


def check_probe_count_gate(failures):
    """探针条目被删到只剩 1 项时必须直接 harness 失败，且不执行任何探针。

    `main()` 只在 `probes is PROBES` 时校验条目数，因此这里替换模块全局，
    再以 `probes=None` 调用，让被测分支真正生效。
    """
    original = run_all.PROBES
    run_all.PROBES = [("ok1", OK, "正常通过")]
    try:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = run_all.main(out_root=OUT, run_selftest=False)
    finally:
        run_all.PROBES = original
    text = buffer.getvalue()
    executed = bool(parse_marks(text))
    ok = rc == 1 and not executed
    print(f"[{'PASS' if ok else 'FAIL'}] 条目数门禁 rc={rc}（期望 1）"
          f" 已执行探针={executed}（期望 False）  "
          "探针被增删时不得静默少跑")
    if not ok:
        failures.append(f"条目数门禁 rc={rc} 期望 1；执行探针={executed} 期望 False")


def main() -> int:
    print(f"自检输出目录: {OUT}")
    failures = []
    check_classify(failures)
    check_aggregate(failures)
    check_scenarios(failures)
    check_probe_count_gate(failures)

    print("\n--- 自检汇总 ---")
    if failures:
        for item in failures:
            print("[FAIL] " + item)
        print("分类或汇总逻辑已失效：ENV_BLOCKED 可能被用来掩盖 harness 失败，"
              "本次探针结论不得作为证据。")
        return 1
    print(f"全部 {len(CLASSIFY_CASES) + len(AGGREGATE_CASES) + len(SCENARIOS) + 1} "
          "项判据通过：ENV_BLOCKED 仅由规范化标记签发，harness 失败优先于环境阻塞。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
