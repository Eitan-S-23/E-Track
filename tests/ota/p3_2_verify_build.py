"""P3-2 独立验收核验：生产构建产物 → finalize 镜像 → 板上 dump 三方闭合。

真机段（p3_2_verify_realdevice.py）只能证明「板上镜像 == INFO 摘要」。本脚本补上
第三条腿：用当前仓库源码构建出的 App bin，经 Tools/etu_pack.py finalize 按取证
时的冻结参数回填 fw_header，重算 SHA-256 并与包内冻结的板上 dump 逐字节比较。
三方闭合后，INFO 帧内的 32B 摘要才真正绑定到「本仓库源码构建出的那一份镜像」。

同时核验产品符号在生产 ELF 中的落位（身份链进了 text、快照进了 BSS、无测试符号
泄漏），证明取证路径走的是生产链路而非测试桩。

fail-closed：产物缺失、finalize 失败、哈希不一致均非零退出。
"""

import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "docs" / "acceptance-contracts" / "P3-2-v1"
DUMP = BUNDLE / "artifacts" / "realdevice" / "app_dump.bin"
NM_DUMP = BUNDLE / "artifacts" / "build" / "nm-app-gcc-symbols.txt"
BUILD = ROOT / "MDK-ARM_F435" / "cmake-generated" / "build-gcc-release"
APP_BIN = BUILD / "app-gcc" / "X-Track-App-GCC.bin"
OUT = ROOT / ".cache" / "p3-2-acceptance" / "finalize-repro.bin"

# 取证时冻结的 finalize 参数（实现方证据 §7.1，验收独立复算必须逐项相同）
FINALIZE_ARGS = ["--ver-name", "3.2.0", "--build-ts", "1788375368",
                 "--hw-rev", "1", "--layout-id", "1", "--min-boot", "1"]

# 生产符号期望：名字与所在段（nm 类型字母），地址不锚定（允许链接布局变化）
EXPECT_SYMBOLS = {
    "ota_device_identity_get": "T",
    "_ZL14s_ble_identity": "b",
    "_ZL21ble_env_info_providerP14ota_ble_info_t": "t",
    "_ZL18ble_env_get_deviceP15ota_sd_device_t": "t",
}
# 测试符号泄漏白名单（生产 API，名字里恰好含 test）
TEST_SYMBOL_ALLOW = ("bot_scsi_test_unit", "lv_obj_hit_test")

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


def need(path, hint):
    if not path.is_file():
        raise SystemExit(f"P3_2_BUILD=FAIL 缺少 {hint}: {path}")
    return path


need(DUMP, "包内冻结板上 dump")
need(NM_DUMP, "包内冻结 nm 符号表")
need(APP_BIN, "生产 App bin（先执行合同内 CMake 构建命令）")

dump = DUMP.read_bytes()
app = APP_BIN.read_bytes()

print("== A. finalize 镜像独立复算 ==")
ck(len(app) == len(dump), "生产 App bin 与板上 dump 长度一致", len(app), len(dump))
OUT.parent.mkdir(parents=True, exist_ok=True)
cmd = [sys.executable, "-X", "utf8", "-B", str(ROOT / "Tools" / "etu_pack.py"),
       "finalize", "--app", str(APP_BIN), "--out", str(OUT), *FINALIZE_ARGS]
p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, errors="replace")
ck(p.returncode == 0, "etu_pack.py finalize 退出码 0", p.returncode, 0)
if p.returncode != 0:
    print(p.stdout + p.stderr)
    print(f"P3_2_BUILD checks={checks} failures={len(failures)}")
    print("P3_2_BUILD=FAIL")
    raise SystemExit(1)

repro = OUT.read_bytes()
repro_sha = hashlib.sha256(repro).hexdigest()
dump_sha = hashlib.sha256(dump).hexdigest()
ck(len(repro) == len(dump), "复算 finalize 镜像长度一致", len(repro), len(dump))
ck(repro == dump, "复算 finalize 镜像 == 板上 dump（逐字节，三方闭合）",
   repro_sha, dump_sha)

# 与未 finalize 的源 bin 的差异必须只落在 fw_header 96B 内
diff_off = [i for i in range(min(len(app), len(repro))) if app[i] != repro[i]]
ck(all(0x400 <= i < 0x460 for i in diff_off),
   "finalize 仅改写 0x400..0x45F（fw_header 96B），镜像正文未被触碰",
   (min(diff_off, default=None), max(diff_off, default=None)), "0x400..0x45F")
ck(len(diff_off) > 0, "finalize 确实回填了 fw_header（存在差异字节）",
   len(diff_off), ">0")

print("== B. 生产符号落位 ==")
nm = NM_DUMP.read_text(encoding="utf-8", errors="replace")
rows = {}
for line in nm.splitlines():
    m = re.match(r"^([0-9a-f]{8})\s+(\S)\s+(\S+)$", line.strip())
    if m:
        rows[m.group(3)] = (m.group(1), m.group(2))
for sym, want_type in EXPECT_SYMBOLS.items():
    got = rows.get(sym)
    ck(got is not None and got[1] == want_type,
       f"符号 {sym} 存在且落在预期段（nm 类型 {want_type}）",
       got, want_type)
addr_identity = rows.get("ota_device_identity_get", ("", ""))[0]
ck(addr_identity.startswith("080"), "身份链实现落在内部 Flash（0x08xxxxxx）",
   addr_identity, "080xxxxx")
addr_snapshot = rows.get("_ZL14s_ble_identity", ("", ""))[0]
ck(addr_snapshot.startswith("200"), "快照状态落在 SRAM（0x20xxxxxx）",
   addr_snapshot, "200xxxxx")

leaked = [s for s in rows
          if re.search(r"(^|_)test(_|$)|__test|unittest", s)
          and s not in TEST_SYMBOL_ALLOW]
ck(not leaked, "生产 ELF 无测试符号泄漏（白名单外）", leaked, [])
ck(len(rows) > 1000, "nm 符号表完整（非截断证据）", len(rows), ">1000")

print()
print(f"P3_2_BUILD checks={checks} failures={len(failures)}")
print(f"app_bin_bytes={len(app)} finalize_sha256={repro_sha}")
print(f"board_dump_sha256={dump_sha}")
print(f"fw_header_diff_bytes={len(diff_off)} symbols={len(rows)}")
if failures:
    print("P3_2_BUILD=FAIL")
    raise SystemExit(1)
print("P3_2_BUILD=PASS")
