"""`-fstack-usage` 可行性验证（整改清单第 3 项）+ 插桩非单调性实证（第 4 项）。

回答三个问题：
  Q1  arm-none-eabi-gcc 13.3 能否为 OTA 调用链产出可用的 .su 数据？
      每个函数的 qualifier 是 static / dynamic / bounded？
  Q2  按调用链求和得到的静态上界是多少？与 OTA_STACK_RESERVE=8192B 的关系？
  Q3  插桩构型（P2_6_TEST_ENABLE）的逐函数栈帧与生产构型相比，
      是否恒 >= 生产（裁定阻断 2 质疑的单调性假设）？
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import out_dir, require_tools, tool_version  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = out_dir("stack_usage")
# 源文件用绝对路径；.o/.su/.elf 一律落在 OUT，不污染受 Git 跟踪的探针目录。
SRC = [str(HERE / n) for n in ("ota_chain.c", "support.c")]
CHAIN = ["ota_apply", "ota_stage_verify", "ota_hash_block", "ota_read_chunk",
         "ota_sink_bytes"]

BASE = ["arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-ffreestanding",
        "-nostdlib", "-fstack-usage", "-c"]

failures = []


def sh(cmd):
    return subprocess.run(cmd, cwd=OUT, capture_output=True, text=True)


def check(cond, msg):
    if not cond:
        failures.append(msg)
    return bool(cond)


def build(tag, opt, defines):
    """编译并解析 .su。返回 {func: (bytes, qualifier)}。"""
    out = OUT / tag
    out.mkdir(parents=True, exist_ok=True)
    su = {}
    for src in SRC:
        obj = out / (Path(src).stem + ".o")
        proc = sh(BASE + [opt] + defines + ["-o", str(obj), src])
        if proc.returncode != 0:
            failures.append(f"{tag} 编译 {Path(src).name} 失败:\n{proc.stderr}")
            return None, None
        # gcc 把 .su 放在 -o 指定的目录
        sf = obj.with_suffix(".su")
        if not sf.exists():
            failures.append(f"{tag} 未生成 {sf.name}")
            return None, None
        for line in sf.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                name = parts[0].split(":")[-1]
                su[name] = (int(parts[1]), parts[2].strip())
    # 反汇编用于观察内联/尾调用差异
    elf = out / "probe.elf"
    link = sh(["arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb",
               "-ffreestanding", "-nostdlib", "-Wl,-e,main", opt] + defines
              + ["-o", str(elf)] + SRC)
    dis = sh(["arm-none-eabi-objdump", "-d", str(elf)]).stdout if \
        link.returncode == 0 else ""
    return su, dis


def chain_sum(su):
    """按调用链求和。缺项视为 0 并记为缺失。"""
    total, missing = 0, []
    for f in CHAIN:
        if f in su:
            total += su[f][0]
        else:
            missing.append(f)
    return total, missing


def present_funcs(dis):
    return set(re.findall(r"^[0-9a-f]+ <([^>]+)>:", dis, re.M))


print("=== Q1: -fstack-usage 产出可用性 ===")
require_tools("arm-none-eabi-gcc", "arm-none-eabi-objdump")
print(f"工具链: {tool_version('arm-none-eabi-gcc')}")
print(f"输出目录: {OUT}")
prod_su, prod_dis = build("prod_O2", "-O2", [])
test_su, test_dis = build("test_O2", "-O2", ["-DP2_6_TEST_ENABLE"])
prod_o0, prod_o0_dis = build("prod_O0", "-O0", [])

if prod_su:
    print(f"{'函数':<20} {'字节':>6}  qualifier")
    for f in CHAIN:
        if f in prod_su:
            b, q = prod_su[f]
            print(f"{f:<20} {b:>6}  {q}")
        else:
            print(f"{f:<20} {'--':>6}  （已内联，无独立栈帧）")
    quals = {q for (_, q) in prod_su.values()}
    check(quals <= {"static", "bounded"},
          f"[Q1] 出现 dynamic qualifier（VLA/alloca，静态求和不可用）: {quals}")
    print(f"出现的 qualifier 集合: {sorted(quals)}")
    print(f".su 覆盖到的函数数: {len(prod_su)}")

print("\n=== Q2: 调用链静态求和上界 ===")
if prod_su and prod_o0:
    t2, m2 = chain_sum(prod_su)
    t0, m0 = chain_sum(prod_o0)
    print(f"-O2 生产构型 链上求和 = {t2} B"
          f"{'   （内联消失: ' + ','.join(m2) + '）' if m2 else ''}")
    print(f"-O0 生产构型 链上求和 = {t0} B"
          f"{'   缺: ' + ','.join(m0) if m0 else ''}")
    print(f"OTA_STACK_RESERVE = 8192 B；-O0 求和占比 = {t0 * 100.0 / 8192:.1f}%")
    check(t0 > 0, "[Q2] -O0 求和为 0，说明 .su 解析失败")
    # 关键：内联会让部分函数在 .su 里消失，纯按"链上函数逐个查表"会漏算
    check(bool(m2) or t2 > 0, "[Q2] -O2 求和异常")
    if m2:
        print(f"[注意] -O2 下 {len(m2)} 个链上函数已无独立 .su 条目 —— "
              f"逐函数查表求和会漏算，必须以实际存在的函数为准")

print("\n=== Q3: 插桩 vs 生产 逐函数栈帧比较（裁定阻断 2） ===")
snap_su, snap_dis = build("test_snap_O2", "-O2",
                          ["-DP2_6_TEST_ENABLE", "-DP2_6_SNAPSHOT"])
big_su, big_dis = build("test_big_O2", "-O2",
                        ["-DP2_6_TEST_ENABLE", "-DP2_6_SNAPSHOT_BIG"])


def compare(label, base_su, base_dis, other_su, other_dis):
    """逐函数比较两构型栈帧，返回 (插桩更大, 插桩更小, 相同, 仅base, 仅other)。"""
    allf = sorted(set(base_su) | set(other_su))
    print(f"\n--- {label} ---")
    print(f"{'函数':<22} {'生产':>8} {'插桩':>8}  关系")
    bigger = smaller = equal = 0
    for f in allf:
        pb = base_su.get(f, (None,))[0]
        tb = other_su.get(f, (None,))[0]
        if pb is None or tb is None:
            rel = "仅一侧存在（内联结构不同）"
        elif tb > pb:
            rel = "插桩更大"
            bigger += 1
        elif tb < pb:
            rel = "插桩更小 ← 反例"
            smaller += 1
        else:
            rel = "相同"
            equal += 1
        print(f"{f:<22} {str(pb):>8} {str(tb):>8}  {rel}")
    bf, of = present_funcs(base_dis), present_funcs(other_dis)
    only_base = sorted(bf - of)
    only_other = sorted(of - bf)
    print(f"仅生产构型有独立函数体: {only_base if only_base else '无'}")
    print(f"仅插桩构型有独立函数体: {only_other if only_other else '无'}")
    print(f"逐函数：插桩更大 {bigger}，插桩更小 {smaller}，相同 {equal}")
    return bigger, smaller, equal, only_base, only_other


results = []
if prod_su and test_su:
    results.append(("仅计数插桩",
                    compare("构型 A：仅计数插桩 (P2_6_TEST_ENABLE)",
                            prod_su, prod_dis, test_su, test_dis)))
if prod_su and snap_su:
    results.append(("计数+快照插桩",
                    compare("构型 B：计数 + 96B 观测快照 (更接近真实插桩)",
                            prod_su, prod_dis, snap_su, snap_dis)))
if prod_su and big_su:
    results.append(("计数+大快照插桩",
                    compare("构型 C：计数 + 512B 快照置于中间层 (改变内联决策)",
                            prod_su, prod_dis, big_su, big_dis)))

print("\n--- 单调性裁决 ---")
any_violation = False
for label, (bigger, smaller, equal, only_base, only_other) in results:
    # 单调性成立 = 没有任何函数插桩更小，且没有函数只在生产侧独立存在
    ok = (smaller == 0 and not only_base)
    print(f"{label:<16} 插桩恒 >= 生产: {ok}"
          f"{'' if ok else '   ← 观察到反例'}")
    if not ok:
        any_violation = True

# 顶层链上总量对比（真正决定 SP 下探深度的量）
if prod_su and test_su and snap_su and big_su:
    t_prod = chain_sum(prod_su)[0]
    print(f"\n链上求和: 生产={t_prod}B  仅计数={chain_sum(test_su)[0]}B  "
          f"+96B快照={chain_sum(snap_su)[0]}B  "
          f"+512B快照={chain_sum(big_su)[0]}B")
    # 逐构型报告 .su 条目集合，展示内联结构是否翻转
    for lbl, su in (("生产", prod_su), ("仅计数", test_su),
                    ("+96B快照", snap_su), ("+512B快照", big_su)):
        chain_present = [f for f in CHAIN if f in su]
        print(f"  {lbl:<10} 链上仍有独立 .su 条目: {chain_present}")

print(f"\n[结论] 是否观察到「插桩栈帧 < 生产栈帧」或函数体消失的反例: "
      f"{any_violation}")
if any_violation:
    print("        → 裁定阻断 2 成立（实测反例）：插桩构型与生产构型之间"
          "不存在编译器保证的单调关系，")
    print("          不能用插桩峰值直接当生产峰值上界；C16 必须要求两构型"
          "各自出 .su 并逐函数比较。")
else:
    print("        → 本轮两种插桩强度下均未出现反例。这不构成编译器保证，"
          "C16 仍须逐轮实测比较。")

# fail-closed：本脚本的记录结论是「三种插桩强度下均无反例」（any_violation=False）。
# 这正是后续要写 scan2/scan3/scan4 定向构造反例的原因 —— C16 判据的实证反例由
# scan4.py 给出（ota_apply 992B→520B），不在本脚本。
# 结论翻转说明工具链或构型已变，必须复核后重写 research，不得静默通过。
EXPECT_VIOLATION = False
check(any_violation == EXPECT_VIOLATION,
      f"[单调性] 本轮 any_violation={any_violation} 与记录结论 "
      f"{EXPECT_VIOLATION} 不一致。结论已失效，必须复核构型与工具链后重新裁定。")
check(len(results) == 3,
      f"[单调性] 应比较 3 种插桩构型, 实际 {len(results)} 种（构建失败会漏比较）")
if any_violation == EXPECT_VIOLATION:
    print("        与记录结论一致：本构型无法构造反例，反例见 scan4.py。")

print("\n=== 汇总 ===")
if failures:
    for f in failures:
        print("[FAIL] " + f)
    print(f"失败 {len(failures)} 项")
    sys.exit(1)
print("探针执行完成（结论见上，Q3 结果决定 C16 判据写法）")
