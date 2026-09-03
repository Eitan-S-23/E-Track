"""P3-2 独立验收核验：host harness 的 fail-closed 静态属性与鉴别力证据。

两部分互补：
  A/B/C 段 —— 对 harness 源码做静态属性核验（每次复跑重新计算），确认它不可能
             在实现有缺陷时仍然打印通过：退出码绑定 failures、编译开启 -Werror、
             链接真实产品源而非副本、无 fail-open 逃生分支。
  D 段    —— 把 C 源内 5 组 golden 期望数组与 tests/ota-vectors/expected.json
             逐字节独立核对，证明断言锚定的是冻结向量而不是自证常量；并核对
             .etu base_sha8 与 raw 域的同源关系（OTA-XC-IMAGE-IDENTITY）。
  E 段    —— 读取本包冻结的注错反证日志，确认三处红线注错各自把 harness 打红，
             且不是因编译错误变红。

fail-closed：任一断言失败即非零退出；无任何无条件汇总字段。
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "docs" / "acceptance-contracts" / "P3-2-v1"
C_SRC = ROOT / "tests" / "ota" / "test_ota_device_info.c"
PY_RUNNER = ROOT / "tests" / "ota" / "test_ota_device_info.py"
PRODUCT_SRC = ROOT / "Libraries" / "OTA" / "ota_device_info.c"
VECTORS = ROOT / "tests" / "ota-vectors" / "expected.json"
PROBE_LOG = BUNDLE / "commands" / "mutation-probe.log"

# fail-open 逃生模式（出现即视为门禁被削弱）
FAIL_OPEN = (
    r"\|\|\s*true",
    r"\|\|\s*:",
    r"continue-on-error",
    r"set\s+\+e",
    r"except\s+Exception\s*:\s*\n\s*pass",
    r"check\s*=\s*False",
)

failures = []
checks = 0


def ck(cond, label, got=None, want=None):
    global checks
    checks += 1
    if cond:
        print(f"  ok   {label}" + (f" = {got!r}" if got is not None else ""))
    else:
        failures.append(f"{label}: got={got!r} want={want!r}")
        print(f"  FAIL {label}: got={got!r} want={want!r}")


def read(path):
    if not path.is_file():
        raise SystemExit(f"P3_2_HARNESS=FAIL 缺少文件: {path}")
    return path.read_text(encoding="utf-8")


c_text = read(C_SRC)
py_text = read(PY_RUNNER)

print("== A. C harness 退出码绑定真实失败计数 ==")
ck(re.search(r"return\s+failures\s*==\s*0\s*\?\s*0\s*:\s*1\s*;", c_text) is not None,
   "main 退出码 = (failures==0 ? 0 : 1)", True, True)
ck(re.search(r'printf\("P3_2_OTA_DEVICE_INFO checks=%d failures=%d', c_text) is not None,
   "汇总行同时输出 checks 与 failures（可外部核对）", True, True)
ck(re.search(r"failures\+\+", c_text) is not None and c_text.count("failures++") >= 2,
   "断言失败路径递增 failures", c_text.count("failures++"), ">=2")
ck(re.search(r"P3_2_OTA_DEVICE_INFO_ALL\s*=\s*PASS", c_text) is None,
   "C 源内不存在无条件 ALL=PASS 常量输出", True, True)
called = re.findall(r"^\s{4}(t\d[a-z0-9_]*)\(\);", c_text, re.M)
ck(len(called) >= 7, "main 实际调用的用例组数量", len(called), ">=7")

print("== B. Python 运行器不吞失败 ==")


def call_exprs(text, needle):
    """按配对括号切出完整调用表达式（内层 str(...) 不会截断）。"""
    out = []
    for m in re.finditer(re.escape(needle) + r"\(", text):
        depth, i = 0, m.end() - 1
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    out.append(text[m.start():i + 1])
                    break
            i += 1
    return out


run_calls = call_exprs(py_text, "subprocess.run")
ck(len(run_calls) >= 2, "存在编译与运行两处 subprocess.run", len(run_calls), ">=2")
ck(all("check=True" in c for c in run_calls),
   "全部 subprocess.run 带 check=True（非零退出即抛出）",
   sum("check=True" in c for c in run_calls), len(run_calls))
idx_run = py_text.rfind("subprocess.run")
idx_pass = py_text.find("P3_2_OTA_DEVICE_INFO_ALL=PASS")
ck(0 < idx_run < idx_pass, "ALL=PASS 打印发生在被测程序成功返回之后",
   (idx_run, idx_pass), "run < print")
ck("-Werror" in py_text, "GCC 路径开启 -Werror", True, True)
ck("/WX" in py_text, "MSVC 路径开启 /WX", True, True)
for pat in ("-Wall", "-Wextra"):
    ck(pat in py_text, f"编译开启 {pat}", True, True)

print("== C. 链接真实产品源、无 fail-open 逃生 ==")
ck('"Libraries/OTA/ota_device_info.c"' in py_text,
   "直接链接产品源 Libraries/OTA/ota_device_info.c", True, True)
for real in ("boot/src/boot_fw_header.c", "boot/src/boot_sha256.c",
             "Libraries/EEPROM/eeprom_bcb.c"):
    ck(f'"{real}"' in py_text, f"链接真实依赖 {real}", True, True)
ck(PRODUCT_SRC.is_file(), "被测产品源存在于产品目录（非测试内副本）", True, True)
for pat in FAIL_OPEN:
    hits = [n for n, t in (("C", c_text), ("PY", py_text))
            if re.search(pat, t)]
    ck(not hits, f"无 fail-open 模式 /{pat}/", hits, [])

print("== D. golden 期望数组与冻结向量逐字节核对 ==")
exp = json.loads(read(VECTORS))
vec = exp["vectors"]


def c_array(name, size):
    m = re.search(r"%s\[%d\]\s*=\s*\{(.*?)\};" % (re.escape(name), size),
                  c_text, re.S)
    if not m:
        return None
    vals = re.findall(r"0x([0-9a-fA-F]{2})", m.group(1))
    return "".join(v.lower() for v in vals)


expect_map = {
    ("RAW_SHA_OLD", 32): vec["toy-old.bin"]["file_sha256"],
    ("HDR_SHA_OLD", 32): vec["toy-old.bin"]["fw_header"]["image_sha256"],
    ("RAW_SHA_NEW", 32): vec["toy-new.bin"]["file_sha256"],
    ("HDR_SHA_NEW", 32): vec["toy-new.bin"]["fw_header"]["image_sha256"],
    ("BASE_SHA8_OLD", 8): vec["toy-patch.etu"]["outer_header"]["base_sha8"],
}
for (name, size), want in expect_map.items():
    got = c_array(name, size)
    ck(got == want.lower(), f"{name} == expected.json 对应值", got, want.lower())

ck(vec["toy-patch.etu"]["outer_header"]["base_sha8"].lower()
   == vec["toy-old.bin"]["file_sha256"][:16].lower(),
   ".etu base_sha8 == 基线镜像 raw SHA 前 8B（身份域同源，非双零域）",
   vec["toy-patch.etu"]["outer_header"]["base_sha8"].lower(),
   vec["toy-old.bin"]["file_sha256"][:16].lower())
ck(vec["toy-old.bin"]["file_sha256"].lower()
   != vec["toy-old.bin"]["fw_header"]["image_sha256"].lower(),
   "冻结向量本身即证明 raw 域与双零域互异", True, True)
ck(re.search(r"MODEL_EXPECTED\[8\]\s*=\s*\{\s*'E',\s*'-',\s*'T',\s*'r',"
             r"\s*'a',\s*'c',\s*'k',\s*'\\0'\s*\}", c_text) is not None,
   "冻结 model 期望值为 E-Track + NUL 恰 8B（OTA-XC-DEVICE-MODEL）", True, True)

print("== E. 注错反证（读取本包冻结日志）==")
probe = read(PROBE_LOG)
ck("P3_2_MUTATION_PROBE=PASS" in probe, "反证脚本整体判定 PASS", True, True)
mut_ids = re.findall(r"=== (M\d) ", probe)
ck(len(mut_ids) == 3, "三处红线注错各执行一次", mut_ids, ["M1", "M2", "M3"])
red = re.findall(r"退出码=(\d+) 编译错误=(True|False)", probe)
ck(len(red) == 3, "三处注错各记录退出码与编译错误标志", len(red), 3)
ck(all(rc != "0" for rc, _ in red), "三处注错全部把 harness 打红（退出码非 0）",
   [rc for rc, _ in red], "all != 0")
ck(all(ce == "False" for _, ce in red),
   "变红原因是断言失败而非编译错误", [ce for _, ce in red], "all False")
m_orig = re.search(r"原文件 SHA-256 = ([0-9a-f]{64})", probe)
m_back = re.search(r"还原后 SHA-256 = ([0-9a-f]{64})", probe)
ck(m_orig is not None and m_back is not None and m_orig.group(1) == m_back.group(1),
   "注错后产品源逐字节复原（哈希一致）",
   m_back.group(1)[:16] if m_back else None,
   m_orig.group(1)[:16] if m_orig else None)
tail = probe.rsplit("=== 复跑（还原后）===", 1)
ck(len(tail) == 2 and "failures=0" in tail[1],
   "还原后复跑重新全绿（证明红是注错所致）", True, True)

print()
print(f"P3_2_HARNESS checks={checks} failures={len(failures)}")
if failures:
    print("P3_2_HARNESS=FAIL")
    raise SystemExit(1)
print("P3_2_HARNESS=PASS")
