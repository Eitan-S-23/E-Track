# 扫描插桩位置 x 快照大小，检查是否存在 ota_apply 栈帧「插桩 < 生产」的反例。
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import out_dir, require_tools  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = out_dir("stack_usage", "scan")
SRC = tuple(str(HERE / n) for n in ("ota_chain.c", "support.c"))
BASE = ["arm-none-eabi-gcc","-mcpu=cortex-m4","-mthumb","-ffreestanding",
        "-nostdlib","-fstack-usage","-c"]

# 本扫描的记录结论（fail-closed 基线）：21 个配置全部未出现 ota_apply 变小。
# 该扫描是"未能构造反例"的负结果，真正的反例由 scan4.py 给出。
EXPECT_NEG = 0

def su_of(tag, defines, opt="-O2"):
    out = OUT/tag; out.mkdir(parents=True, exist_ok=True)
    su = {}
    for src in SRC:
        obj = out/(Path(src).stem+".o")
        p = subprocess.run(BASE+[opt]+defines+["-o",str(obj),src],
                           cwd=OUT, capture_output=True, text=True)
        if p.returncode: return None
        for line in obj.with_suffix(".su").read_text().splitlines():
            parts = line.split("\t")
            if len(parts)>=3: su[parts[0].split(":")[-1]] = int(parts[1])
    return su

require_tools("arm-none-eabi-gcc")
base = su_of("base", [])
if base is None: raise SystemExit("生产基线编译失败")
print(f"生产基线 ota_apply = {base['ota_apply']} B")
print(f"{'插桩配置':<34} {'ota_apply':>10} {'链上和':>8}  判定")
rows=[]
for sz in (8,32,96,256,512,1024,2048):
    for pos,macro in (("内层","P2_6_SNAP_INNER"),("中层","P2_6_SNAPSHOT_BIG"),
                      ("哈希层","P2_6_SNAPSHOT")):
        d = ["-DP2_6_TEST_ENABLE", f"-D{macro}", f"-DP2_6_SNAP_SIZE={sz}"]
        su = su_of(f"{macro}_{sz}", d)
        if su is None: continue
        a = su.get("ota_apply",0)
        tot = sum(su.get(f,0) for f in ("ota_apply","ota_stage_verify",
                  "ota_hash_block","ota_read_chunk","ota_sink_bytes"))
        verdict = "插桩更小 <== 反例" if a < base["ota_apply"] else ""
        rows.append((a,verdict))
        print(f"{pos+' snap='+str(sz):<34} {a:>10} {tot:>8}  {verdict}")
neg = [r for r in rows if r[1]]
print(f"\n扫描 {len(rows)} 个配置，出现 ota_apply 栈帧小于生产的配置数: {len(neg)}")
if len(rows) != 21:
    print(f"[FAIL] 应扫描 21 个配置，实际 {len(rows)}（有配置编译失败被跳过）")
    raise SystemExit(1)
if len(neg) != EXPECT_NEG:
    print(f"[FAIL] 反例数 {len(neg)} 与记录结论 {EXPECT_NEG} 不一致，"
          f"结论已失效，必须复核后重写 research 与 C16 判据")
    raise SystemExit(1)
print(f"与记录结论一致（反例数 {EXPECT_NEG}）：本构型无法构造反例，"
      f"反例见 scan4.py")
