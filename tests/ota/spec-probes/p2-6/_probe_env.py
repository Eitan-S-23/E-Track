"""P2-6 Spec 探针共用环境：输出目录定位与工具链前置检查。

约束（写入边界）：探针只允许把生成物写入仓库内 `.cache/p2-6-spec-probe-run/`
（`.gitignore:104` 的 `/.cache/` 已忽略）。受 Git 跟踪的探针目录只放源文件、
runner 与期望判据，不得被运行过程污染。

约束（fail-closed）：工具链缺失必须是显式失败并返回非零退出码，不得静默跳过后
在汇总里报"通过"。缺工具链时探针的正确结论是 `ENV_BLOCKED`，由调用方按验收
合同处理，探针自身不得自行降级为 PASS。

约束（ENV_BLOCKED 只能由本模块签发）：`ENV_BLOCKED` 是"环境缺工具链"这一**特定**
结论，不是"非零退出码"的同义词。判定必须同时满足退出码 == `ENV_BLOCKED_EXIT_CODE`
且输出含 `ENV_BLOCKED_LINE_PREFIX` 开头的行。只看退出码会把 harness 故障误分类：
Python 在"脚本文件不存在"和非法解释器参数时也返回 2（Python 3.13.12 实测；
2026-08-16 定向复核阻断 1 就是被"脚本不存在返回 2"骗过的）。语法错误、未捕获
异常等故障返回 1，`sys.exit(n)` 则原样透传任意码 —— 所以非零退出码与"环境缺
工具链"之间不存在可靠映射，必须靠标记行区分。标记的**签发**（`require_tools`）与**识别**
（`is_env_blocked_output`）都在本模块，避免调用方自行硬编码字符串而漂移。
"""
import shutil
import subprocess
import sys
from pathlib import Path

# tests/ota/spec-probes/p2-6/_probe_env.py -> parents[4] 即仓库根
REPO_ROOT = Path(__file__).resolve().parents[4]
PROBE_ROOT = Path(__file__).resolve().parent
OUT_ROOT = REPO_ROOT / ".cache" / "p2-6-spec-probe-run"

# ENV_BLOCKED 的规范化标记（纯 ASCII，便于 grep 与跨 locale 稳定）。
# 退出码 2 单独不足以证明"环境缺工具链"：`python missing.py` 与非法解释器参数也返回 2
# （Python 3.13.12 实测），而语法错误等故障返回 1，`sys.exit(n)` 还能透传任意码。
# 因此汇总器必须同时校验退出码与本标记行；两者缺一即归 harness 失败。
ENV_BLOCKED_EXIT_CODE = 2
ENV_BLOCKED_MARKER = "P2_6_PROBE_ENV_BLOCKED"
ENV_BLOCKED_LINE_PREFIX = f"[ENV_BLOCKED] {ENV_BLOCKED_MARKER} "

# 日志编码必须与终端 locale 解耦：中文 Windows 默认 cp936，落盘/重定向的证据
# 会变成 mojibake，且同一脚本在不同机器上产出不同字节，无法按 SHA-256 绑定。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, OSError):
        pass


def out_dir(*parts: str) -> Path:
    """返回 `.cache/p2-6-spec-probe-run/<parts...>/`，并确保目录存在。"""
    path = OUT_ROOT.joinpath(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def require_tools(*tools: str) -> None:
    """任一工具缺失即以 `ENV_BLOCKED_EXIT_CODE` 退出，并签发规范化标记行。

    标记行必须先 flush 再退出：`capture_output=True` 时 stdout 是管道（块缓冲），
    若解释器在异常路径上没能 flush，汇总器会看到"退出码 2 但无标记"，
    按 fail-closed 规则归入 harness 失败 —— 宁可误报故障，不可漏报。
    """
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        print(f"{ENV_BLOCKED_LINE_PREFIX}工具链缺失: {', '.join(missing)}")
        print("             探针无法执行，按验收合同应记 ENV_BLOCKED，不得记 PASS。")
        sys.stdout.flush()
        sys.exit(ENV_BLOCKED_EXIT_CODE)


def is_env_blocked_output(text: str) -> bool:
    """判定子进程输出是否携带本模块签发的 ENV_BLOCKED 标记。

    只认**行首**前缀，不做子串包含匹配：探针日志里出现"ENV_BLOCKED"这个词
    （例如说明性文字或末 15 行回显）不得被当成标记。
    """
    return any(
        line.startswith(ENV_BLOCKED_LINE_PREFIX) for line in text.splitlines()
    )


def tool_version(tool: str) -> str:
    """返回工具版本首行，用于把证据绑定到具体工具链版本。"""
    try:
        proc = subprocess.run([tool, "--version"], capture_output=True, text=True)
        return (proc.stdout or proc.stderr).splitlines()[0].strip()
    except (OSError, IndexError):
        return "<未知>"
