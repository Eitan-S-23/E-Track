"""定向验证「插桩使父函数栈帧变小」（裁定阻断 2 的实证反例）。

真实机制：P2-6 需要按函数归属栈帧，被内联的函数在 .su 里没有独立条目，
因此插桩构型往往给采集点所在函数加 noinline（或因体积/调用结构变化被 gcc
自行拒绝内联）。一旦子函数不再内联，父函数就不再折叠子函数的局部缓冲，
父函数 .su 随之变小 —— 而链上真实峰值可能反而更深。
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import out_dir, require_tools  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = out_dir("stack_usage", "scan4")
BASE = ["arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-ffreestanding",
        "-nostdlib", "-fstack-usage", "-c"]
SRC = tuple(str(HERE / n) for n in ("ota_chain4.c", "support.c"))
CHAIN = ["ota_apply", "ota_stage_verify", "ota_hash_block", "ota_read_chunk"]


def su_of(tag, defines):
    out = OUT / tag
    out.mkdir(parents=True, exist_ok=True)
    su = {}
    for src in SRC:
        obj = out / (Path(src).stem + ".o")
        p = subprocess.run(BASE + ["-O2"] + defines + ["-o", str(obj), src],
                           cwd=OUT, capture_output=True, text=True)
        if p.returncode:
            print(f"[{tag}] 编译 {src} 失败:\n{p.stderr}")
            return None
        for line in obj.with_suffix(".su").read_text().splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                su[parts[0].split(":")[-1]] = int(parts[1])
    return su


require_tools("arm-none-eabi-gcc")
base = su_of("prod", [])
if base is None:
    raise SystemExit("生产基线编译失败")
print("=== 生产构型 ===")
for f in CHAIN:
    print(f"  {f:<20} {base.get(f, '--（已内联，无独立条目）')}")
prod_apply = base["ota_apply"]
prod_total = sum(base.get(f, 0) for f in CHAIN)
print(f"  ota_apply = {prod_apply} B；链上求和 = {prod_total} B\n")

CASES = [
    ("仅计数", ["-DP2_6_TEST_ENABLE"]),
    ("计数+采集点 noinline", ["-DP2_6_TEST_ENABLE", "-DP2_6_NOINLINE_PROBE"]),
    ("计数+noinline+96B快照",
     ["-DP2_6_TEST_ENABLE", "-DP2_6_NOINLINE_PROBE", "-DP2_6_SNAPSHOT",
      "-DP2_6_SNAP_SIZE=96"]),
    ("计数+noinline+512B快照",
     ["-DP2_6_TEST_ENABLE", "-DP2_6_NOINLINE_PROBE", "-DP2_6_SNAPSHOT",
      "-DP2_6_SNAP_SIZE=512"]),
]

print(f"{'插桩构型':<26} {'ota_apply':>10} {'链上求和':>9}  逐函数关系")
violations = []
scanned = 0
for label, defs in CASES:
    su = su_of(label.replace("+", "_").replace(" ", ""), defs)
    if su is None:
        continue
    scanned += 1
    a = su.get("ota_apply", 0)
    total = sum(su.get(f, 0) for f in CHAIN)
    rel = []
    for f in CHAIN:
        pb, tb = base.get(f), su.get(f)
        if pb is None and tb is not None:
            rel.append(f"{f}:内联→独立({tb})")
        elif pb is not None and tb is not None and tb < pb:
            rel.append(f"{f}:{pb}→{tb} 变小")
        elif pb is not None and tb is not None and tb > pb:
            rel.append(f"{f}:{pb}→{tb} 变大")
    shrunk = a < prod_apply
    if shrunk:
        violations.append((label, a, total))
    print(f"{label:<26} {a:>10} {total:>9}  {'; '.join(rel) or '无变化'}"
          f"{'   ← 父帧变小(反例)' if shrunk else ''}")

print(f"\n出现「插桩后 ota_apply 栈帧 < 生产」的构型: "
      f"{len(violations)}/{len(CASES)}")
for label, a, total in violations:
    print(f"  [反例] {label}: ota_apply {prod_apply} → {a} "
          f"（小 {prod_apply - a} B）；同时链上求和 {prod_total} → {total} "
          f"（{'更深' if total > prod_total else '更浅'}）")
if violations:
    print("\n[裁定阻断 2 成立] 插桩构型某函数的栈帧可以小于生产构型对应函数，")
    print("  故不能用插桩构型逐函数栈帧当生产构型的上界；必须两构型各自出 .su")
    print("  并逐函数比较，且父帧变小往往伴随链上真实峰值变深。")

# fail-closed：本脚本是 C16「两构型各自出 .su 逐函数比较」判据的唯一实证来源。
# 记录结论：4 个构型中 3 个触发反例，ota_apply 992B→520B（小 472B），
# 同时链上求和 992B→1000/1032/1448B（更深）。任何偏离都必须复核后重写
# research 与 C16 判据，不得静默沿用旧结论。
EXPECT_VIOLATIONS = 3
EXPECT_PROD_APPLY = 992
EXPECT_SHRUNK_APPLY = 520
fail = []
if scanned != len(CASES):
    fail.append(f"应比较 {len(CASES)} 个插桩构型，实际 {scanned}（有构型编译失败）")
if len(violations) != EXPECT_VIOLATIONS:
    fail.append(f"反例构型数 {len(violations)} 与记录结论 {EXPECT_VIOLATIONS} 不一致")
if prod_apply != EXPECT_PROD_APPLY:
    fail.append(f"生产 ota_apply={prod_apply}B 与记录值 {EXPECT_PROD_APPLY}B 不一致")
bad = [(l, a) for l, a, _ in violations if a != EXPECT_SHRUNK_APPLY]
if bad:
    fail.append(f"反例 ota_apply 值与记录值 {EXPECT_SHRUNK_APPLY}B 不一致: {bad}")
deeper = [(l, t) for l, _, t in violations if t <= prod_total]
if deeper:
    fail.append(f"反例应同时使链上求和更深（>{prod_total}B），未满足: {deeper}")
if fail:
    for item in fail:
        print("[FAIL] " + item)
    print("结论已失效：C16 判据的实证依据必须重新裁定，不得沿用。")
    raise SystemExit(1)
print(f"\n与记录结论一致：{EXPECT_VIOLATIONS}/{len(CASES)} 构型触发反例，"
      f"ota_apply {EXPECT_PROD_APPLY}→{EXPECT_SHRUNK_APPLY}B，链上求和全部更深。")
