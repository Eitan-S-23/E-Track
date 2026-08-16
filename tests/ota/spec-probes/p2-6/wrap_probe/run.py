"""ARM GCC `--wrap` 最小跨翻译单元验证（裁定阻断 4 / 整改清单第 5 项）。

覆盖裁定要求的 8 项：
  1. __wrap_* 进入最终 ELF/map
  2. __real_* 正确转发（不残留未定义引用）
  3. 参数/返回值/调用顺序不变（real_pool_seq 指纹 + last_size + ret_nonnull）
  4. 正例增量为 0
  5. 负例增量非零
  6. wrapper 关闭后生产构型符号全消失
  7. --gc-sections 不错误移除 wrapper
  8. 明确无 LTO

核心待答问题：--wrap=lv_mem_alloc 能否拦住 LVGL 内部入口 lv_mem_buf_get？
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _probe_env import out_dir, require_tools, tool_version  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = out_dir("wrap_probe")
# 源文件用绝对路径，生成物一律落在 OUT，避免污染受 Git 跟踪的探针目录。
SRC = [str(HERE / n) for n in
       ("lv_mem_stub.c", "lv_tlsf_stub.c", "p2_6_wrap.c", "main.c")]

# 实测约束：wrapper 定义集合必须与 --wrap= 集合严格一一对应。
# 定义了 __wrap_X 却不传 --wrap=X 时，__real_X 是未定义引用，链接失败。
# 因此用 -DP2_6_WRAP_MEM / -DP2_6_WRAP_TLSF 门控 wrapper 定义，与命令行同步。
CFG_MEM = (["-DP2_6_TEST_ENABLE", "-DP2_6_WRAP_MEM"],
           ["-Wl,--wrap=lv_mem_alloc", "-Wl,--wrap=lv_mem_realloc",
            "-Wl,--wrap=lv_mem_free"])
CFG_TLSF = (["-DP2_6_TEST_ENABLE", "-DP2_6_WRAP_TLSF"],
            ["-Wl,--wrap=lv_tlsf_malloc", "-Wl,--wrap=lv_tlsf_realloc",
             "-Wl,--wrap=lv_tlsf_free"])
CFG_BOTH = (CFG_MEM[0] + ["-DP2_6_WRAP_TLSF"], CFG_MEM[1] + CFG_TLSF[1])
CFG_PROD = ([], [])

MEM_SYMS = ["__wrap_lv_mem_alloc", "__wrap_lv_mem_realloc", "__wrap_lv_mem_free",
            "P2_6_lv_mem_alloc_calls", "P2_6_lv_mem_realloc_calls",
            "P2_6_lv_mem_free_calls"]
TLSF_SYMS = ["__wrap_lv_tlsf_malloc", "__wrap_lv_tlsf_realloc",
             "__wrap_lv_tlsf_free", "P2_6_lv_tlsf_malloc_calls",
             "P2_6_lv_tlsf_realloc_calls", "P2_6_lv_tlsf_free_calls",
             "P2_6_last_tlsf_size", "P2_6_last_tlsf_ret"]
ALL_SYMS = MEM_SYMS + TLSF_SYMS

failures = []


def sh(cmd):
    return subprocess.run(cmd, cwd=OUT, capture_output=True, text=True)


def check(cond, msg):
    if not cond:
        failures.append(msg)
    return bool(cond)


# ---------------- HOST 组：行为验证 ----------------
def host_run(name, cfg):
    defines, wraps = cfg
    exe = OUT / f"{name}.exe"
    cmd = ["gcc", "-O2", "-Wall", "-Wextra", "-o", str(exe)] + SRC \
        + defines + wraps
    proc = sh(cmd)
    if proc.returncode != 0:
        failures.append(f"HOST {name} 编译失败:\n{proc.stdout}{proc.stderr}")
        return None
    run = sh([str(exe)])
    if run.returncode != 0:
        failures.append(f"HOST {name} 运行失败 rc={run.returncode}\n{run.stderr}")
        return None
    return run.stdout


ROW = re.compile(
    r"^(\S+)\s+mem\[a=(\d+) r=(\d+) f=(\d+)\]\s+tlsf\[a=(\d+) r=(\d+) f=(\d+)\]"
    r"\s+real_a=(\d+)")


def parse(out):
    rows = {}
    for line in out.splitlines():
        m = ROW.match(line)
        if m:
            rows[m.group(1)] = tuple(int(m.group(i)) for i in range(2, 9))
    seq = re.search(r"real_pool_seq=(\d+)\s+real_pool_last_size=(\d+)", out)
    rows["_seq"] = (int(seq.group(1)), int(seq.group(2))) if seq else None
    return rows


print("=== HOST 组：行为验证 ===")
require_tools("gcc", "arm-none-eabi-gcc", "arm-none-eabi-nm",
              "arm-none-eabi-objdump")
print(f"HOST 工具链: {tool_version('gcc')}")
print(f"ARM 工具链: {tool_version('arm-none-eabi-gcc')}")
print(f"输出目录: {OUT}")
out = {k: host_run(f"host_{k}", c) for k, c in
       (("mem", CFG_MEM), ("tlsf", CFG_TLSF), ("both", CFG_BOTH),
        ("prod", CFG_PROD))}

for k in ("mem", "tlsf", "both", "prod"):
    if out[k]:
        print(f"--- {k} ---")
        print(out[k], end="")

r_mem = parse(out["mem"]) if out["mem"] else {}
r_tlsf = parse(out["tlsf"]) if out["tlsf"] else {}
r_both = parse(out["both"]) if out["both"] else {}
r_prod = parse(out["prod"]) if out["prod"] else {}

print("\n--- 判据 ---")

# 4. 正例增量为 0（三种插桩构型都必须成立）
for k, r in (("mem", r_mem), ("tlsf", r_tlsf), ("both", r_both)):
    a = r.get("A_no_alloc")
    check(a == (0,) * 7, f"[正例] {k} 场景 A 应全 0, 实测 {a}")
print("正例(场景 A)全零:", all(r.get("A_no_alloc") == (0,) * 7
                                for r in (r_mem, r_tlsf, r_both)))

# 5. 负例增量非零
if r_mem:
    b = r_mem.get("B_external_lv_mem_alloc")
    check(b and b[0] == 1 and b[6] == 1,
          f"[负例] mem 构型场景 B 应 mem_a=1 real_a=1, 实测 {b}")
    d = r_mem.get("D_lv_mem_realloc")
    check(d and d[1] == 1, f"[负例] mem 构型场景 D 应 mem_r=1, 实测 {d}")
    e = r_mem.get("E_lv_mem_free")
    check(e and e[2] == 1, f"[负例] mem 构型场景 E 应 mem_f=1, 实测 {e}")

if r_tlsf:
    b = r_tlsf.get("B_external_lv_mem_alloc")
    check(b and b[3] == 1, f"[负例] tlsf 构型场景 B 应 tlsf_a=1, 实测 {b}")
    d = r_tlsf.get("D_lv_mem_realloc")
    check(d and d[4] == 1, f"[负例] tlsf 构型场景 D 应 tlsf_r=1, 实测 {d}")
    e = r_tlsf.get("E_lv_mem_free")
    check(e and e[5] == 1, f"[负例] tlsf 构型场景 E 应 tlsf_f=1, 实测 {e}")

# 核心结论：lv_mem 层的同翻译单元盲区 vs lv_tlsf 层的覆盖
c_mem = r_mem.get("C_internal_lv_mem_buf_get") if r_mem else None
c_tlsf = r_tlsf.get("C_internal_lv_mem_buf_get") if r_tlsf else None
if c_mem and c_tlsf:
    check(c_mem[6] == 1, f"场景 C 真实池应发生 1 次分配, 实测 real_a={c_mem[6]}")
    check(c_mem[0] == 0,
          f"[核心] 预期 --wrap=lv_mem_alloc 拦不到同 TU 内部入口(增量 0), "
          f"实测 mem_a={c_mem[0]}")
    check(c_tlsf[3] == 1,
          f"[核心] 预期 --wrap=lv_tlsf_malloc 能拦到内部入口(增量 1), "
          f"实测 tlsf_a={c_tlsf[3]}")
    print(f"[核心结论] LVGL 内部入口 lv_mem_buf_get -> 真实池分配 1 次；"
          f"lv_mem 层拦截增量={c_mem[0]}（盲区），"
          f"lv_tlsf 层拦截增量={c_tlsf[3]}（覆盖）")

# both 构型下同时观察两层：内部入口只被下层拦到
c_both = r_both.get("C_internal_lv_mem_buf_get") if r_both else None
if c_both:
    check(c_both[0] == 0 and c_both[3] == 1,
          f"[核心] both 构型场景 C 应 mem_a=0 且 tlsf_a=1, 实测 {c_both}")
    print(f"both 构型场景 C: mem_a={c_both[0]}  tlsf_a={c_both[3]}")

# 3. 调用顺序不变：四种构型的真实实现序列指纹必须完全一致
seqs = {k: r.get("_seq") for k, r in
        (("mem", r_mem), ("tlsf", r_tlsf), ("both", r_both), ("prod", r_prod))
        if r}
uniq = set(seqs.values())
check(len(uniq) == 1 and None not in uniq,
      f"[顺序保真] 各构型 real_pool_seq/last_size 不一致: {seqs}")
print(f"调用序列指纹(各构型应一致): {seqs}")

# 3. 参数/返回值保真
for k, o in (("tlsf", out["tlsf"]), ("both", out["both"])):
    if o:
        m = re.search(r"forward_fidelity\s+last_tlsf_size=(\d+)\s+ret_nonnull=(\d)", o)
        check(m is not None, f"[保真] {k} 缺 forward_fidelity 行")
        if m:
            # 最后一次到达 tlsf 层的 malloc 是场景 C 的 48（D 走 realloc 路径）
            check(m.group(1) == "48",
                  f"[保真] {k} 入参应原样传递 48, 实测 {m.group(1)}")
            check(m.group(2) == "1", f"[保真] {k} 返回值应非空原样传回")
            print(f"{k} 转发保真: last_tlsf_size={m.group(1)} "
                  f"ret_nonnull={m.group(2)}")

# 生产构型必须仍然功能正常（真实池确实被调用过）
if r_prod:
    check(r_prod.get("B_external_lv_mem_alloc", (0,) * 7)[6] == 1,
          "生产构型场景 B 真实池未被调用")
    check(all(v == 0 for v in r_prod.get("A_no_alloc", (1,))[:6]),
          "生产构型不应有任何 wrapper 计数")
    print("生产构型: 真实池正常工作, wrapper 计数恒 0")


# ---------------- ARM 组：链接验证 ----------------
print("\n=== ARM 组：链接验证 ===")
ARM_BASE = ["arm-none-eabi-gcc", "-mcpu=cortex-m4", "-mthumb", "-O2",
            "-ffreestanding", "-nostdlib",
            "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections",
            "-Wl,-e,main"]


def arm_build(name, cfg):
    defines, wraps = cfg
    elf = OUT / f"{name}.elf"
    mapf = OUT / f"{name}.map"
    cmd = ARM_BASE + ["-o", str(elf)] + SRC + ["-DP2_6_FREESTANDING"] \
        + defines + wraps + [f"-Wl,-Map={mapf}"]
    proc = sh(cmd)
    if proc.returncode != 0:
        failures.append(f"ARM {name} 链接失败:\n{proc.stdout}{proc.stderr}")
        return None, None
    nm = sh(["arm-none-eabi-nm", str(elf)]).stdout
    mp = mapf.read_text(encoding="utf-8", errors="replace")
    return nm, mp


def sym_present(nm, name):
    return re.search(rf"^\S+\s+\S+\s+{re.escape(name)}$", nm, re.M) is not None


nm_both, mp_both = arm_build("arm_both", CFG_BOTH)
nm_prod, mp_prod = arm_build("arm_prod", CFG_PROD)

if nm_both:
    # 1 + 7. 全部 wrapper 与计数器进入最终 ELF，--gc-sections 未误删
    missing = [s for s in ALL_SYMS if not sym_present(nm_both, s)]
    check(not missing, f"[ELF] 插桩构型缺符号(--gc-sections 误删?): {missing}")
    print(f"插桩构型 ELF 符号命中: {len(ALL_SYMS) - len(missing)}/{len(ALL_SYMS)}"
          f"{'' if not missing else '  缺:' + str(missing)}")

    # 2. __real_* 不残留未定义引用
    unresolved = re.findall(r"^\s+U (__real_\S+)$", nm_both, re.M)
    check(not unresolved, f"[__real_] 未被 ld 解析: {unresolved}")
    print(f"__real_* 未解析残留: {unresolved if unresolved else '无'}")

    # 1. map 中可见全部 6 个 wrapper
    mp_missing = [s for s in ALL_SYMS if s.startswith("__wrap_")
                  and s not in mp_both]
    check(not mp_missing, f"[map] 缺 wrapper 命中: {mp_missing}")
    print(f"map 中 wrapper 命中: {6 - len(mp_missing)}/6")

if nm_prod:
    # 6. 生产构型全部测量符号消失
    leaked = [s for s in ALL_SYMS if sym_present(nm_prod, s)]
    check(not leaked, f"[生产构型] 残留测量符号: {leaked}")
    print(f"生产构型残留测量符号: {leaked if leaked else '无（14 个全部消失）'}")
    leaked_mp = [s for s in ("__wrap_", "__real_") if s in (mp_prod or "")]
    check(not leaked_mp, f"[生产构型] map 残留 wrap 记号: {leaked_mp}")
    print(f"生产构型 map 残留 __wrap_/__real_: "
          f"{leaked_mp if leaked_mp else '无'}")

# 8. 明确无 LTO
lto = [a for a in ARM_BASE + CFG_BOTH[0] + CFG_BOTH[1] if "flto" in a]
check(not lto, f"探针命令行含 LTO 选项: {lto}")
print(f"命令行 LTO 选项: {lto if lto else '无（未启用 LTO）'}")

# 反汇编级覆盖检查：盲区必须在指令层可见，而不只是计数为 0。
#
# 实测发现（比"符号解析不重定向"更彻底的盲区来源）：
#   -O2 下 lv_mem_buf_get 对同 TU 的 lv_mem_alloc 调用被尾调用折叠/内联消除，
#   最终指令直接 b.w __wrap_lv_tlsf_malloc —— 调用点在链接前就不存在了。
#   因此 --wrap=lv_mem_alloc 不是"拦到了但没重定向"，而是"根本没有可拦的调用点"，
#   nm/map 里也看不到任何痕迹。这同时是裁定阻断 2 所述"插桩改变内联/尾调用"的实例。
print("\n--- 反汇编级覆盖检查 ---")
if nm_both:
    dis = sh(["arm-none-eabi-objdump", "-d", str(OUT / "arm_both.elf")]).stdout
    (OUT / "arm_both.dis").write_text(dis, encoding="utf-8")

    def callees(func):
        """返回该函数体内所有分支/调用目标（bl 与 b/b.w 尾调用都算）。"""
        m = re.search(rf"^[0-9a-f]+ <{re.escape(func)}>:\n((?:.*\n)*?)\n",
                      dis, re.M)
        if m is None:
            return None
        return re.findall(r"\b(?:bl|b|b\.w|bl\.w)\s+[0-9a-f]+ <([^>+]+)",
                          m.group(1))

    c_buf = callees("lv_mem_buf_get")
    c_alloc = callees("lv_mem_alloc")
    check(c_buf is not None and c_alloc is not None,
          f"反汇编未找到目标函数: buf_get={c_buf} alloc={c_alloc}")
    if c_buf is not None and c_alloc is not None:
        # 核心：上层 wrapper 完全不在调用链上
        check("__wrap_lv_mem_alloc" not in c_buf,
              f"[反汇编] lv_mem_buf_get 不应经过 __wrap_lv_mem_alloc, 实测 {c_buf}")
        # 下层 wrapper 必然在调用链上（无论上层调用点是否被内联消除）
        check("__wrap_lv_tlsf_malloc" in c_buf,
              f"[反汇编] lv_mem_buf_get 应最终到达 __wrap_lv_tlsf_malloc, "
              f"实测 {c_buf}")
        check("__wrap_lv_tlsf_malloc" in c_alloc,
              f"[反汇编] lv_mem_alloc 应被重定向到 __wrap_lv_tlsf_malloc, "
              f"实测 {c_alloc}")
        inlined = "lv_mem_alloc" not in c_buf
        print(f"lv_mem_buf_get  分支目标 -> {c_buf}")
        print(f"lv_mem_alloc    分支目标 -> {c_alloc}")
        print(f"上层调用点是否被内联/尾调用消除: {inlined}"
              f"{'（--wrap=lv_mem_alloc 无可拦截的调用点）' if inlined else ''}")

print("\n=== 汇总 ===")
if failures:
    for f in failures:
        print("[FAIL] " + f)
    print(f"失败 {len(failures)} 项")
    sys.exit(1)
print("全部检查通过（8 项裁定要求 + 核心盲区结论）")
