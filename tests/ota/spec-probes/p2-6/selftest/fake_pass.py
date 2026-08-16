"""假探针：正常通过（自检正例基线）。

存在意义：自检必须能区分"分类逻辑坏了"和"所有输入都被判失败"。若只有负例，
把 `classify()` 写成恒返回 `HARNESS_FAIL` 也能让四个负例全过。
"""
print("fake probe: everything is fine")
raise SystemExit(0)
