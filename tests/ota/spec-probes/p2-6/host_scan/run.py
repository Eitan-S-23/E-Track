"""StackInfo 扫描算法与栈底 guard 相互作用的宿主验证（fail-closed runner）。

原始探针靠人工看 ✓/✗，不构成可复现证据。本 runner 把五个场景的期望值写死并
按退出码判定，任何偏离都必须复核后重写 research 与提示词判据。

结论对应的提示词判据：
  S2 失效  → guard 若落在栈区最低字，StackInfo 扫描恒返回满栈，C3 门禁失去鉴别力。
             **现行方案据此把 guard 移出栈区**（外置 guard 区），不是给扫描加偏移。
  S3 有效  → 只用于证明 S2 的成因确实是 guard 落在 i=0（把 guard 排除后读数即恢复）。
             `skip_words` 偏移修法已被 2026-08-16 独立复核裁定**作废**：偏移常量写错
             同样静默出错。本场景是成因对照实验，**不得**当成推荐修法引用。
  S4 失效  → BLANK 常量必须与实际填充哨兵同步，否则扫描恒为满栈。
  S5 可检出 → guard 被踩破即可判定溢出，是外置 guard 方案的兜底手段。
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import out_dir, require_tools, tool_version  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = out_dir("host_scan")
SRC = HERE / "host_scan_test.c"

# 记录结论（fail-closed 基线）：栈区 8192B，实际用量 1024B。
EXPECT = {
    "STACK_BYTES": 8192,
    "S1_scan": 1024,      # 基准：扫描准确
    "S2_scan": 8192,      # guard 在 i=0 → 恒满栈（失效）
    "S3_scan": 1024,      # 排除 guard 字后读数恢复 → 证明 S2 成因（修法本身已作废）
    "S4_scan": 8192,      # BLANK 未同步 → 恒满栈（失效）
    "S5_guard_intact": 0,  # guard 被踩破 → 溢出可检出
}
NOTE = {
    "S1_scan": "基准：非零哨兵 + 无 guard，扫描应准确",
    "S2_scan": "guard 落在 i=0，扫描立即命中 → 恒返回满栈（失效）",
    "S3_scan": "排除 guard 字后读数恢复准确 → 证明 S2 成因（该偏移修法已作废）",
    "S4_scan": "BLANK 未与哨兵常量同步 → i=0 即命中 → 恒返回满栈（失效）",
    "S5_guard_intact": "guard 字被完全覆盖 → intact=0，溢出可检出",
}


def main() -> int:
    require_tools("gcc")
    print(f"HOST 工具链: {tool_version('gcc')}")
    print(f"输出目录: {OUT}")

    exe = OUT / "host_scan_test.exe"
    build = subprocess.run(
        ["gcc", "-O2", "-Wall", "-Wextra", "-o", str(exe), str(SRC)],
        cwd=OUT, capture_output=True, text=True)
    if build.returncode != 0:
        print(f"[FAIL] 编译失败:\n{build.stdout}{build.stderr}")
        return 1
    if build.stderr.strip():
        print(f"[FAIL] 编译有告警（-Wall -Wextra 必须干净）:\n{build.stderr}")
        return 1

    run = subprocess.run([str(exe)], cwd=OUT, capture_output=True, text=True)
    if run.returncode != 0:
        print(f"[FAIL] 运行失败 rc={run.returncode}\n{run.stderr}")
        return 1

    got = {}
    for line in run.stdout.splitlines():
        m = re.match(r"^(\w+)=(0x[0-9A-Fa-f]+|\d+)$", line.strip())
        if m:
            got[m.group(1)] = int(m.group(2), 0)

    failures = []
    for key, want in EXPECT.items():
        if key not in got:
            failures.append(f"{key} 缺失（探针输出格式已变）")
            continue
        mark = "PASS" if got[key] == want else "FAIL"
        if mark == "FAIL":
            failures.append(f"{key} 期望 {want}, 实测 {got[key]}")
        note = NOTE.get(key, "")
        print(f"[{mark}] {key:<18} = {got[key]:<6}（期望 {want}）"
              f"{'  ' + note if note else ''}")
    print(f"guard 字终值 = {got.get('S5_guard_word', 0):#010x}")

    print("\n=== 汇总 ===")
    if failures:
        for item in failures:
            print("[FAIL] " + item)
        print("结论已失效：栈底 guard 与扫描算法的相互作用必须重新验证，"
              "不得沿用旧结论。")
        return 1
    print("五个场景全部与记录结论一致："
          "guard 落在栈区最低字会让扫描恒返回满栈（故 guard 必须外置），"
          "BLANK 必须与哨兵同步，guard 被踩破可检出溢出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
