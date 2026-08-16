"""定向寻找「插桩后父函数栈帧变小」的反例（裁定阻断 2）。

机制假设：插桩使子函数代码体积增大 -> gcc 拒绝内联 -> 子函数获得独立栈帧，
父函数不再折叠子函数的局部缓冲 -> 父函数 .su 变小。
父函数变小并不意味着实际峰值 SP 变浅（链上总和可能反而变大），
所以「用插桩构型某函数的栈帧当生产对应函数的上界」是不成立的。
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import out_dir, require_tools  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = out_dir("stack_usage", "scan3")
BASE = ["arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-ffreestanding",
        "-nostdlib", "-fstack-usage", "-c"]
SRC = tuple(str(HERE / n) for n in ("ota_chain3.c", "support.c"))
CHAIN = ["ota_apply", "ota_stage_verify", "ota_hash_block", "ota_read_chunk"]

# 本扫描的记录结论（fail-closed 基线）：7 档 BULK 全部未出现反例。
# 单纯增大插桩体积不足以让父帧变小，必须显式 noinline 采集点（见 scan4.py）。
EXPECT_NEG = 0


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
base = su_of("base", [])
if base is None:
    raise SystemExit("生产基线编译失败")
print("生产构型 .su:", {k: v for k, v in sorted(base.items())})
print(f"生产 ota_apply = {base['ota_apply']} B\n")

print(f"{'插桩强度(BULK)':<16} {'ota_apply':>10} {'链上求和':>10}  "
      f"{'链上独立条目':<44} 判定")
found = []
scanned = 0
for bulk in (1, 2, 4, 8, 16, 32, 64):
    su = su_of(f"bulk{bulk}", ["-DP2_6_TEST_ENABLE",
                               f"-DP2_6_NOTE_BULK={bulk}"])
    if su is None:
        continue
    scanned += 1
    apply_b = su.get("ota_apply", 0)
    total = sum(su.get(f, 0) for f in CHAIN)
    present = [f for f in CHAIN if f in su]
    smaller = apply_b < base["ota_apply"]
    if smaller:
        found.append((bulk, apply_b, total))
    print(f"{'BULK=' + str(bulk):<16} {apply_b:>10} {total:>10}  "
          f"{str(present):<44} {'← 父帧变小(反例)' if smaller else ''}")

print(f"\n生产链上求和 = {sum(base.get(f, 0) for f in CHAIN)} B")
print(f"出现「插桩后 ota_apply 栈帧小于生产」的配置: {len(found)}/7")
for bulk, a, t in found:
    print(f"  BULK={bulk}: ota_apply {base['ota_apply']} -> {a} "
          f"（小 {base['ota_apply'] - a} B），但链上求和 "
          f"{sum(base.get(f, 0) for f in CHAIN)} -> {t}")

# fail-closed：记录结论是 0/7。偏离即说明结论失效，必须复核后重写 research。
if scanned != 7:
    print(f"[FAIL] 应扫描 7 档 BULK，实际 {scanned}（有配置编译失败被跳过）")
    raise SystemExit(1)
if len(found) != EXPECT_NEG:
    print(f"[FAIL] 反例数 {len(found)} 与记录结论 {EXPECT_NEG} 不一致，结论已失效")
    raise SystemExit(1)
print(f"与记录结论一致（反例数 {EXPECT_NEG}）：仅增大插桩体积不足以构造反例，"
      f"反例见 scan4.py")
