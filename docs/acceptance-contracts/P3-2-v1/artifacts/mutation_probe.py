"""P3-2 独立验收：对 host harness 做注错反证，证明其具备鉴别力而非橡皮章。

三处注错各针对派工书一条红线；每处注错都保持可编译（不制造 -Werror 编译错误），
使"变红"只能来自断言失败而非编译失败。try/finally 保证无条件还原并校验哈希。
"""

import hashlib
import subprocess
import sys
from pathlib import Path

# 冻结于证据包内，向上找仓库根（AGENTS.md 为标记），使脚本在原地可直接复跑。
ROOT = next(d for d in Path(__file__).resolve().parents
            if (d / "AGENTS.md").is_file())
SRC = ROOT / "Libraries" / "OTA" / "ota_device_info.c"
RUNNER = ROOT / "tests" / "ota" / "test_ota_device_info.py"

orig = SRC.read_bytes()
orig_sha = hashlib.sha256(orig).hexdigest()
print(f"原文件 SHA-256 = {orig_sha}")

MUTATIONS = [
    (
        "M1 摘要域越界：raw 域结果被 fw_header 双零域覆盖（派工书红线：禁止混用两域）",
        b"""    memcpy(state->info.model, k_ota_device_model,""",
        b"""    memcpy(state->info.image_sha256, header.image_sha256, 32);
    memcpy(state->info.model, k_ota_device_model,""",
    ),
    (
        "M2 冻结 model 漂移：\"E-Track\" 改 \"X-Track\"（OTA-XC-DEVICE-MODEL）",
        b"""    'E', '-', 'T', 'r', 'a', 'c', 'k', '\\0'""",
        b"""    'X', '-', 'T', 'r', 'a', 'c', 'k', '\\0'""",
    ),
    (
        "M3 fail-closed 失效：BCB 仲裁 ERROR 不再拒绝（派工书：IO 失败必须 fail closed）",
        b"""        return OTA_DEVICE_ERR_BCB_IO;""",
        b"""        (void)0;""",
    ),
]


def run_harness():
    p = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(RUNNER)],
        cwd=str(ROOT), capture_output=True, text=True, errors="replace",
    )
    out = p.stdout + p.stderr
    compile_err = ("error:" in out) or ("Error" in out and "checks=" not in out)
    return p.returncode, out, compile_err


results = []
try:
    print("\n=== 基线（未注错）===")
    rc, out, _ = run_harness()
    tail = [ln for ln in out.splitlines() if "checks=" in ln or "_ALL=" in ln]
    print(f"退出码={rc} | " + " | ".join(tail))
    results.append(("BASELINE", rc, tail, False))
    if rc != 0:
        raise SystemExit("基线未通过，注错反证无意义")

    for name, needle, repl in MUTATIONS:
        if orig.count(needle) != 1:
            raise SystemExit(f"注错锚点命中数异常({orig.count(needle)}): {name}")
        SRC.write_bytes(orig.replace(needle, repl))
        rc, out, cerr = run_harness()
        tail = [ln for ln in out.splitlines() if "checks=" in ln or "_ALL=" in ln
                or "FAIL" in ln][:6]
        print(f"\n=== {name} ===")
        print(f"退出码={rc} 编译错误={cerr}")
        for ln in tail:
            print("  " + ln)
        results.append((name, rc, tail, cerr))
        SRC.write_bytes(orig)
finally:
    SRC.write_bytes(orig)
    back_sha = hashlib.sha256(SRC.read_bytes()).hexdigest()
    print(f"\n还原后 SHA-256 = {back_sha}")
    if back_sha != orig_sha:
        print("P3_2_MUTATION_PROBE=FAIL（还原失败，必须人工检查）")
        raise SystemExit(2)
    print("还原一致：源文件逐字节复原")

print("\n=== 复跑（还原后）===")
rc, out, _ = run_harness()
tail = [ln for ln in out.splitlines() if "checks=" in ln or "_ALL=" in ln]
print(f"退出码={rc} | " + " | ".join(tail))

ok = (results[0][1] == 0 and rc == 0
      and all(r[1] != 0 and not r[3] for r in results[1:]))
print()
print(f"P3_2_MUTATION_PROBE={'PASS' if ok else 'FAIL'}")
if not ok:
    raise SystemExit(1)
