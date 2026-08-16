"""假探针：伪 `rc=2` —— 退出码是 2，但没有 `_probe_env` 签发的规范化标记。

覆盖三种最容易蒙混过关的输出形态：

1. 正文里出现 `ENV_BLOCKED` 这个词（说明性文字、末 15 行回显都可能带上）；
2. **旧格式**的 `[ENV_BLOCKED] 工具链缺失: ...` 行 —— 这是 2026-08-16 之前
   `require_tools()` 的真实输出格式。若有人把 `require_tools()` 回退成旧实现，
   标记会消失，此时必须落到 harness 失败一侧（fail-closed），
   而不是继续按环境阻塞放行；
3. 退出码恰为 2，与真实环境阻塞完全相同。

真实对应场景：`python 不存在的脚本.py`、非法解释器参数 —— 它们都让 Python
返回 2（3.13.12 实测），与真实环境阻塞的退出码完全撞车。只凭退出码判定就会把
harness 故障报成"工具链缺失"。语法错误等故障返回 1、`sys.exit(n)` 透传任意码，
同样必须落到 harness 失败一侧。
"""
print("some probe stage reported ENV_BLOCKED in the middle of a sentence")
print("[ENV_BLOCKED] 工具链缺失: arm-none-eabi-gcc")
raise SystemExit(2)
