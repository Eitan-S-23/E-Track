"""外置 guard 布局最小链接验证：正例 + 9 类负例。

判据全部来自同目录 `cases.json`（可被验收合同按 SHA-256 绑定），本脚本不内嵌
期望值。三类判据：

  link=ok            正例必须链接成功，且六个符号取到契约地址。
  assert_contains    负例必须链接失败，且命中集合包含指定 ASSERT 编号。
  assert_exact       负例必须链接失败，且命中集合恰好等于给定集合 —— 用于证明
                     某条 ASSERT 自身具备鉴别力，而不是靠其他条目连带失败。
  undefined_symbols  负例必须链接失败，且错误里出现指定未定义符号。

仅确认 rc=1 不算通过：链接失败可能来自 ld 内置的 overlaps/overflow 检查，
那说明我们自己的 ASSERT 没有鉴别力。

生成物一律写入 `.cache/p2-6-spec-probe-run/guard_layout/`，不污染本目录。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import out_dir, require_tools, tool_version  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = out_dir("guard_layout")
GCC = "arm-none-eabi-gcc"
NM = "arm-none-eabi-nm"

CFG = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
CONST = CFG["constants"]
ESTACK = int(CONST["estack"], 16)
STACK_LEN = int(CONST["stack_len"])
GUARD_LEN = int(CONST["guard_len"])
HEAP_LEN = int(CONST["heap_len"], 16)
STACK_ADDR = ESTACK - STACK_LEN
GUARD_ADDR = STACK_ADDR - GUARD_LEN

TMPL = (HERE / "layout.ld.tmpl").read_text(encoding="utf-8")

# 脱钩负例：把"由段派生"的符号定义改回独立常量算术。
# A6 一并改 __StackGuardEnd，使 A8 仍然成立，从而把失败面收敛到 A6 一条。
DECOUPLE_VALUE = "_estack - OTA_STACK_RESERVE - 64;"
DECOUPLE_RULES = {
    "A7": [("__StackGuardStart = ADDR(.ota_stack_guard);",
            "__StackGuardStart = " + DECOUPLE_VALUE)],
    "A6": [("__StackLimit      = ADDR(.ota_stack);",
            "__StackLimit      = " + DECOUPLE_VALUE),
           ("__StackGuardEnd   = ADDR(.ota_stack_guard) + SIZEOF(.ota_stack_guard);",
            "__StackGuardEnd   = " + DECOUPLE_VALUE)],
}

failures = []


def check(cond, msg):
    if not cond:
        failures.append(msg)
    return bool(cond)


def selfcheck_constants():
    """cases.json 里的字面地址必须与常量算术一致，防止改常量漏改用例。"""
    want = {"derived_stack_addr": STACK_ADDR, "derived_guard_addr": GUARD_ADDR}
    for key, value in want.items():
        got = int(CONST[key], 16)
        check(got == value,
              f"[cases.json] {key}={got:#x} 与常量算术 {value:#x} 不一致")
    pos = next(c for c in CFG["cases"] if c["name"] == "pos")
    sym = pos["expect"]["symbols"]
    expect = {
        "__StackLimit": STACK_ADDR, "__StackTop": ESTACK,
        "__StackGuardStart": GUARD_ADDR, "__StackGuardEnd": STACK_ADDR,
        "STACK$$Base": STACK_ADDR, "STACK$$Limit": ESTACK,
    }
    for key, value in expect.items():
        check(int(sym[key], 16) == value,
              f"[cases.json] pos.symbols.{key} 与常量算术 {value:#x} 不一致")


def render(case) -> str:
    values = {
        "STACK_LEN": str(STACK_LEN),
        "GUARD_LEN": str(GUARD_LEN),
        "HEAP_LEN": hex(HEAP_LEN),
        "STACK_ADDR": hex(STACK_ADDR),
        "GUARD_ADDR": hex(GUARD_ADDR),
        # 段内填充长度默认引用契约常量；负例只改这一侧以制造脱钩
        "STACK_FILL": "OTA_STACK_RESERVE",
        "GUARD_FILL": "OTA_STACK_GUARD_SIZE",
    }
    values.update(case.get("overrides", {}))
    text = TMPL
    for key, value in values.items():
        text = text.replace(f"@@{key}@@", value)
    assert "@@" not in text, f"{case['name']}: 占位符未全部替换"
    for old, new in DECOUPLE_RULES.get(case.get("decouple"), []):
        assert old in text, f"{case['name']}: 脱钩锚点未命中: {old}"
        text = text.replace(old, new)
    return text


def link(case):
    name = case["name"]
    ld = OUT / f"{name}.ld"
    ld.write_text(render(case), encoding="utf-8")
    elf = OUT / f"{name}.elf"
    cmd = [
        GCC, "-mcpu=cortex-m4", "-mthumb", "-O2", "-ffreestanding", "-nostdlib",
        "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
        f"-T{ld}", "-o", str(elf), str(HERE / "probe_main.c"),
        f"-Wl,-Map={OUT / (name + '.map')}",
    ] + case.get("cflags", [])
    proc = subprocess.run(cmd, cwd=OUT, capture_output=True, text=True)
    return proc, elf


def symbols(elf: Path) -> dict:
    out = subprocess.run([NM, str(elf)], capture_output=True, text=True).stdout
    result = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3:
            result[parts[2]] = int(parts[0], 16)
    return result


def main() -> int:
    require_tools(GCC, NM)
    print(f"工具链: {tool_version(GCC)}")
    print(f"输出目录: {OUT}")
    selfcheck_constants()

    for case in CFG["cases"]:
        name, expect = case["name"], case["expect"]
        proc, elf = link(case)
        err = proc.stdout + proc.stderr

        if expect["link"] == "ok":
            if not check(proc.returncode == 0,
                         f"{name}: 正例应链接成功, rc={proc.returncode}\n{err}"):
                continue
            sym = symbols(elf)
            for key, value in expect["symbols"].items():
                got = sym.get(key)
                check(got == int(value, 16),
                      f"{name}: {key} 期望 {value}, 实测 "
                      f"{'缺失' if got is None else hex(got)}")
            print(f"[PASS] {name}  rc=0  " + "  ".join(
                f"{k}={sym.get(k, 0):#x}" for k in expect["symbols"]))
            continue

        if not check(proc.returncode != 0, f"{name}: 负例应链接失败, 但 rc=0"):
            continue

        hits = sorted(set(re.findall(r"\b(A[1-9])\s*:", err)))
        if "assert_exact" in expect:
            want = sorted(expect["assert_exact"])
            if not check(hits == want,
                         f"{name}: 期望命中集合恰为 {want}, 实际 {hits}"
                         f"\n{err.strip()[:600]}"):
                continue
            print(f"[PASS] {name}  rc={proc.returncode}  命中集合恰为 {hits}"
                  f"（独立负例成立）")
            continue
        if "assert_contains" in expect:
            want = expect["assert_contains"]
            if not check(want in hits,
                         f"{name}: 期望命中 {want}, 实际命中 {hits}"
                         f"\n{err.strip()[:600]}"):
                continue
            print(f"[PASS] {name}  rc={proc.returncode}  命中 {hits}")
            continue
        if "undefined_symbols" in expect:
            missing = [s for s in expect["undefined_symbols"] if s not in err]
            if not check(not missing,
                         f"{name}: 错误输出缺未定义符号 {missing}"
                         f"\n{err.strip()[:600]}"):
                continue
            check(not hits,
                  f"{name}: 该负例应只因未定义符号失败, 但命中了 ASSERT {hits}")
            print(f"[PASS] {name}  rc={proc.returncode}  "
                  f"未定义符号 {expect['undefined_symbols']} 均已出现")
            continue
        failures.append(f"{name}: cases.json 未给出可执行的判据")

    print("\n=== 汇总 ===")
    if failures:
        for item in failures:
            print("[FAIL] " + item)
        print(f"失败 {len(failures)} 项")
        return 1
    total = len(CFG["cases"])
    print(f"全部 {total} 个用例通过"
          f"（1 正例 + {total - 1} 负例，判据来自 cases.json）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
