"""P2-6 Spec 探针统一入口：任一探针失败即整体 rc!=0。

用途：把 P2-6 提示词判据所依赖的全部 Spec 侧实证一次性复现，供验收会话在干净
worktree 中执行并把日志按 SHA-256 绑定进证据包。

用法（仓库根执行）：
    python tests/ota/spec-probes/p2-6/run_all.py

退出码（优先级固定，不可调换）：
    1  至少一个探针 harness 失败（结论失效或 harness 本身坏了）
    2  没有 harness 失败，且至少一个探针真实环境阻塞（ENV_BLOCKED，不得记 PASS）
    0  全部探针与记录结论一致

**为什么 harness 失败必须优先于环境阻塞**：混合出现"真实失败 + 工具链缺失"时，
若先返回 2，调用方会按"补装工具链后重跑"处理，真实失败被环境噪声掩盖。反过来
先返回 1 只会让调用方多做一次复核，不会漏判（2026-08-16 定向复核阻断 1）。

**ENV_BLOCKED 的判定不看裸退出码**：`python 不存在的脚本.py` 与非法解释器参数
也返回 2，语法错误等故障返回 1，`sys.exit(n)` 还能透传任意码（Python 3.13.12
实测）—— 非零退出码与"环境缺工具链"之间没有可靠映射。必须同时满足退出码 ==
`ENV_BLOCKED_EXIT_CODE` 且输出含 `_probe_env.require_tools()` 签发的规范化标记行，
判定由 `_probe_env.is_env_blocked_output()` 统一给出。

自检前置：正式探针之前先运行 `selftest/classification_selftest.py`，用四个负例
证明本文件的分类与汇总逻辑仍然 fail-closed。自检不通过即 rc=1 且**不输出**任何
Spec 结论 —— harness 自身不可信时，"8/8 通过"没有证据价值。
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _probe_env import (  # noqa: E402
    ENV_BLOCKED_EXIT_CODE,
    OUT_ROOT,
    REPO_ROOT,
    is_env_blocked_output,
)

HERE = Path(__file__).resolve().parent
SELFTEST = HERE / "selftest" / "classification_selftest.py"

# 分类标记：只有三种。"非零退出码"不等于"环境阻塞"，也不存在第四种中间态。
MARK_PASS = "PASS"
MARK_ENV_BLOCKED = "ENV_BLOCKED"
MARK_HARNESS_FAIL = "HARNESS_FAIL"

# (探针名, 脚本相对路径, 该探针支撑的提示词判据)
PROBES = [
    ("guard_layout", "guard_layout/run.py",
     "九条链接期 ASSERT 各自具备鉴别力（含 A6 独立负例）+ 两层间接宏必要性"),
    ("wrap_probe", "wrap_probe/run.py",
     "--wrap 拦截层选型：required 层为 lv_tlsf_*；生产构型测量符号全消失"),
    ("stack_usage", "stack_usage/run.py",
     "-fstack-usage 产出可用性 + 本构型无单调性反例"),
    ("stack_usage/scan", "stack_usage/scan.py",
     "插桩位置×快照大小扫描：21 配置无反例"),
    ("stack_usage/scan2", "stack_usage/scan2.py",
     "多调用点构型扫描：18 配置无反例"),
    ("stack_usage/scan3", "stack_usage/scan3.py",
     "插桩体积扫描：7 档 BULK 无反例"),
    ("stack_usage/scan4", "stack_usage/scan4.py",
     "定向反例：采集点 noinline 使父帧 992B→520B，链上求和反而更深"),
    ("host_scan", "host_scan/run.py",
     "guard 落在栈区最低字会让扫描恒返回满栈（故 guard 必须外置）；"
     "BLANK 必须与哨兵常量同步"),
]

# 探针条目数冻结：空列表或被删条目时 `aggregate([])` 会返回 0，
# 汇总输出"通过 0/0"却是成功退出码 —— 典型的静默假通过。
EXPECTED_PROBE_COUNT = 8


def classify(returncode: int, output: str) -> str:
    """把单个探针的执行结果分类为三种标记之一。

    只有"退出码恰为 `ENV_BLOCKED_EXIT_CODE` 且输出含规范化标记行"才是环境阻塞。
    其余一切非零退出（脚本缺失、语法错误、解释器启动错误、断言失败、被信号杀死
    的负值退出码）统一归 harness 失败 —— 分类不确定时必须落到更严重的那一侧。
    """
    if returncode == 0:
        return MARK_PASS
    if returncode == ENV_BLOCKED_EXIT_CODE and is_env_blocked_output(output):
        return MARK_ENV_BLOCKED
    return MARK_HARNESS_FAIL


def aggregate(marks) -> int:
    """按固定优先级把标记序列折叠成整体退出码。

    优先级：harness 失败 > 环境阻塞 > 全部通过。空序列视为 harness 失败，
    避免"没有探针"被当成"全部通过"。
    """
    marks = list(marks)
    if not marks:
        return 1
    if any(mark == MARK_HARNESS_FAIL for mark in marks):
        return 1
    if any(mark == MARK_ENV_BLOCKED for mark in marks):
        return ENV_BLOCKED_EXIT_CODE
    return 0


def run_probe(name: str, script: Path, out_root: Path):
    """执行单个探针，落盘日志，返回 (标记, 退出码, 日志路径, 输出全文)。

    脚本缺失单独给出明确诊断而不依赖解释器的退出码巧合：`python missing.py`
    恰好返回 2，与工具链缺失的退出码相同，靠退出码区分二者是不可靠的。
    """
    log = out_root / (name.replace("/", "_") + ".log")
    log.parent.mkdir(parents=True, exist_ok=True)
    if not script.is_file():
        output = (f"[HARNESS_FAIL] 探针脚本缺失: {script}\n"
                  "这是 harness 故障，不是环境阻塞：脚本本应随仓库入库。\n")
        log.write_text(output, encoding="utf-8")
        return MARK_HARNESS_FAIL, None, log, output
    proc = subprocess.run([sys.executable, str(script)],
                          cwd=REPO_ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="backslashreplace")
    output = proc.stdout + proc.stderr
    log.write_text(output, encoding="utf-8")
    return classify(proc.returncode, output), proc.returncode, log, output


def run_probes(probes, out_root: Path):
    """依次执行探针并打印逐项结论，返回 results 列表。"""
    results = []
    for name, rel, purpose in probes:
        mark, rc, log, output = run_probe(name, HERE / rel, out_root)
        results.append((mark, name, purpose, rc, log))
        rc_text = "-" if rc is None else str(rc)
        try:
            log_text = log.relative_to(REPO_ROOT)
        except ValueError:
            log_text = log
        print(f"[{mark}] {name:<20} rc={rc_text}  日志: {log_text}")
        print(f"         判据: {purpose}")
        if mark != MARK_PASS:
            print("         --- 末 15 行 ---")
            for line in output.splitlines()[-15:]:
                print("         " + line)
    return results


def selftest() -> int:
    """运行分类逻辑自检；返回 0 才允许继续跑正式探针。"""
    print("=== harness 自检（分类与汇总的四个负例）===")
    if not SELFTEST.is_file():
        print(f"[HARNESS_FAIL] 自检脚本缺失: {SELFTEST}")
        return 1
    proc = subprocess.run([sys.executable, str(SELFTEST)],
                          cwd=REPO_ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="backslashreplace")
    for line in (proc.stdout + proc.stderr).splitlines():
        print("  " + line)
    if proc.returncode != 0:
        print(f"[HARNESS_FAIL] 自检失败 rc={proc.returncode}："
              "分类或汇总逻辑已失效，本次运行不输出任何 Spec 结论。")
        return 1
    print("自检通过：ENV_BLOCKED 只能由规范化标记签发，harness 失败优先于环境阻塞。\n")
    return 0


def main(probes=None, out_root=None, run_selftest: bool = True) -> int:
    probes = PROBES if probes is None else probes
    out_root = OUT_ROOT if out_root is None else out_root
    print(f"仓库根: {REPO_ROOT}")
    print(f"生成物根: {out_root}\n")

    if run_selftest and selftest() != 0:
        return 1

    if probes is PROBES and len(probes) != EXPECTED_PROBE_COUNT:
        print(f"[HARNESS_FAIL] 探针条目数 {len(probes)} != 冻结值 "
              f"{EXPECTED_PROBE_COUNT}：条目被增删时必须同步更新 README 与"
              "提示词判据，不得静默少跑。")
        return 1

    results = run_probes(probes, out_root)

    print("\n=== 汇总 ===")
    marks = [row[0] for row in results]
    passed = [mark for mark in marks if mark == MARK_PASS]
    print(f"通过 {len(passed)}/{len(results)}")
    rc = aggregate(marks)
    if rc != 0:
        for mark, name, _, probe_rc, log in results:
            if mark != MARK_PASS:
                rc_text = "-" if probe_rc is None else str(probe_rc)
                print(f"[{mark}] {name} rc={rc_text} 见 {log}")
    if rc == 1:
        print("存在 HARNESS_FAIL：探针结论失效或 harness 本身故障，必须复核后"
              "重写 research 与判据。若同时存在 ENV_BLOCKED，也**先**处理"
              "HARNESS_FAIL，不得用工具链缺失解释真实失败。")
        return 1
    if rc == ENV_BLOCKED_EXIT_CODE:
        print("存在 ENV_BLOCKED 且无 HARNESS_FAIL：工具链缺失，"
              "按验收合同不得记 PASS。")
        return ENV_BLOCKED_EXIT_CODE
    print("全部探针与记录结论一致。日志可直接绑定进证据包（按 SHA-256）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
