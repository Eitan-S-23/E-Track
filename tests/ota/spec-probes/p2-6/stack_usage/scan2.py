# 多调用点构型下，比较生产 vs 插桩的逐函数栈帧，重点看父函数是否变小。
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import out_dir, require_tools  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = out_dir("stack_usage", "scan2")
BASE = ["arm-none-eabi-gcc","-mcpu=cortex-m4","-mthumb","-ffreestanding",
        "-nostdlib","-fstack-usage","-c"]
SRC = tuple(str(HERE / n) for n in ("ota_chain2.c","support2.c","multicall.c"))

# 本扫描的记录结论（fail-closed 基线）：18 个配置全部未出现反例。
EXPECT_NEG = 0

def su_of(tag, defines):
    out = OUT / tag; out.mkdir(parents=True, exist_ok=True)
    su = {}
    for src in SRC:
        obj = out/(Path(src).stem+".o")
        p = subprocess.run(BASE+["-O2"]+defines+["-o",str(obj),src],
                           cwd=OUT, capture_output=True, text=True)
        if p.returncode:
            print(f"[{tag}] 编译 {src} 失败:\n{p.stderr}"); return None
        for line in obj.with_suffix(".su").read_text().splitlines():
            parts = line.split("\t")
            if len(parts)>=3: su[parts[0].split(":")[-1]] = int(parts[1])
    return su

require_tools("arm-none-eabi-gcc")
base = su_of("base", [])
if base is None: raise SystemExit(1)
print("生产构型 .su:")
for k,v in sorted(base.items()): print(f"  {k:<22} {v:>6}")

print(f"\n{'插桩配置':<26} {'变小的函数 (生产 -> 插桩)':<44} 判定")
found = 0
scanned = 0
for sz in (8,32,96,256,512,1024):
    for pos,macro in (("内层","P2_6_SNAP_INNER"),("校验层","P2_6_SNAPSHOT_BIG"),
                      ("哈希层","P2_6_SNAPSHOT")):
        su = su_of(f"{macro}_{sz}", ["-DP2_6_TEST_ENABLE", f"-D{macro}",
                                     f"-DP2_6_SNAP_SIZE={sz}"])
        if su is None: continue
        scanned += 1
        shrunk = [(f, base[f], su[f]) for f in base
                  if f in su and su[f] < base[f]]
        gone = [f for f in base if f not in su and base[f] > 0]
        desc = ", ".join(f"{f}:{a}->{b}" for f,a,b in shrunk) or "-"
        if gone: desc += f"  [消失:{','.join(gone)}]"
        verdict = "反例" if (shrunk or gone) else ""
        if verdict: found += 1
        print(f"{pos+' snap='+str(sz):<26} {desc:<44} {verdict}")
print(f"\n出现「插桩后某函数栈帧更小或独立条目消失」的配置数: {found}/18")

# fail-closed：本扫描的记录结论是 0/18（多调用点构型下构造不出反例）。
# 计数或反例数偏离即说明结论失效，必须复核后重写 research，不得静默通过。
if scanned != 18:
    print(f"[FAIL] 应扫描 18 个配置，实际 {scanned}（有配置编译失败被跳过）")
    raise SystemExit(1)
if found != EXPECT_NEG:
    print(f"[FAIL] 反例数 {found} 与记录结论 {EXPECT_NEG} 不一致，结论已失效")
    raise SystemExit(1)
print(f"与记录结论一致（反例数 {EXPECT_NEG}）：多调用点构型无法构造反例，"
      f"反例见 scan4.py")
