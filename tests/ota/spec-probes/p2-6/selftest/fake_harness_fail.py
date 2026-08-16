"""假探针：普通断言失败（退出码 1）。

对应真实场景：某个 spec 结论已翻转，runner 的 fail-closed 基线不再成立。
分类必须是 `HARNESS_FAIL`，且在与 ENV_BLOCKED 混合时决定整体退出码为 1。
"""
print("fake probe: 冻结基线不再成立")
raise SystemExit(1)
