"""假探针：真实环境阻塞 —— 通过 `require_tools()` 请求一个必然不存在的工具。

标记不在本文件里硬编码：直接调用生产路径的 `require_tools()`，让它签发标记并
退出。这样"签发"和"识别"始终同源 —— 若标记常量或输出格式被改动而
`is_env_blocked_output()` 没跟上，本负例立即失败，不会出现"自检过了但真实
ENV_BLOCKED 被误判成 harness 失败"的漂移。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import require_tools  # noqa: E402

# 该名字含连字符与卡号，任何平台的 PATH 上都不会存在。
require_tools("p2-6-tool-that-must-not-exist")
print("不可达：require_tools 必须已经退出")
raise SystemExit(0)
