"""P3-7 CI 版 fail-closed 反证：四处注错的注入 / 还原。

用法:
  python -X utf8 -B .cache/p3-7-accept/inject_ci.py <0..3>            # 注入
  python -X utf8 -B .cache/p3-7-accept/inject_ci.py <0..3> --restore  # 还原

注入前把原始字节存档到 .cache/p3-7-accept/ci-orig/，还原时按存档字节写回并以
SHA-256 核对。不使用 `git checkout --`。每次注入后自动按 CI 同序跑满 12 条命令
预检，确认红点恰落在目标命令位、且其前置命令全绿（避免 set -e 短路使反证空转）。
"""

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path("D:/github/my/E-Track")
ARCHIVE = ROOT / ".cache" / "p3-7-accept" / "ci-orig"

# (命令位, 目标文件, 原字节, 注错字节)
CASES = [
    (9, "Libraries/OTA/ota_ble_frame.h",
     b"#define OTA_BLE_LEN_ACK_BEGIN 10u",
     b"#define OTA_BLE_LEN_ACK_BEGIN 11u"),
    (10, "USER/HAL/HAL_Bluetooth.cpp",
     b"ota_ble_session_active(&s_ble_session) ? NULL : bt_text_sink,",
     b"bt_text_sink,"),
    # 注：最初选点是把首行 include 改成反斜杠，本地 12 条预检确实红在 cmd11，
    # 但它同时让 arm-none-eabi-gcc 编译失败，CI 在**第 9 步 Build firmware**
    # 就红了，第 10 步整步 skipped——反证空转。改用 `#if 0` 包裹的阳性样本：
    # 预处理器直接丢弃该块，编译不受影响；扫描器是文本匹配，照样命中。
    (11, "USER/HAL/HAL_USB.cpp",
     b'#include "HAL/HAL.h"\r\n',
     b'#include "HAL/HAL.h"\r\n'
     b'#if 0 /* P3-7 fail-closed probe: backslash include sample, not compiled */\r\n'
     b'#include "HAL\\HAL.h"\r\n'
     b'#endif\r\n'),
    (12, "Libraries/OTA/ota_device_info.c",
     b"'E', '-', 'T', 'r', 'a', 'c', 'k', '\\0'",
     b"'F', '-', 'T', 'r', 'a', 'c', 'k', '\\0'"),
]

CMDS = [
    "tests/boot/test_fw_header_vectors.py",
    "tests/boot/test_boot_protocols.py",
    "tests/boot/test_boot_state_machine.py",
    "tests/ota/test_ota_staging.py",
    "tests/ota/test_ota_package.py",
    "tests/ota/test_ota_patch.py",
    "tests/ota/test_ota_ble_frame.py",
    "tests/ota/test_ota_ble_session.py",
    "tests/ota/p3_1_verify_contract_alignment.py",
    "tests/ota/p3_1_verify_text_isolation.py",
    "tests/ota/p3_1_verify_portability.py",
    "tests/ota/test_ota_device_info.py",
]


def sha(b):
    return hashlib.sha256(b).hexdigest().upper()


def precheck(expect_red_at):
    """按 CI 同序跑满 12 条，返回第一个红的命令位（1-based），全绿返回 0。"""
    for i, c in enumerate(CMDS, 1):
        r = subprocess.run([sys.executable, "-X", "utf8", "-B", c],
                           capture_output=True, cwd=str(ROOT))
        if r.returncode != 0:
            print(f"  cmd{i:2d} [RED] rc={r.returncode}  {c}")
            for ln in (r.stdout + r.stderr).decode("utf-8", "replace").strip().splitlines()[-3:]:
                print(f"        | {ln}")
            if i != expect_red_at:
                raise SystemExit(f"预检失败：红点落在 cmd{i}，预期 cmd{expect_red_at}（前置命令被短路，反证无效）")
            return i
        print(f"  cmd{i:2d} [GREEN] {c}")
    return 0


def main():
    idx = int(sys.argv[1])
    restore = "--restore" in sys.argv[2:]
    cmd_no, rel, orig_bytes, bad_bytes = CASES[idx]
    path = ROOT / rel
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    stash = ARCHIVE / f"{idx}-{path.name}"

    if not restore:
        cur = path.read_bytes()
        if cur.count(orig_bytes) != 1:
            raise SystemExit(f"锚点不唯一：{rel} 中出现 {cur.count(orig_bytes)} 次")
        stash.write_bytes(cur)
        assert sha(stash.read_bytes()) == sha(cur)
        print(f"存档 {rel} len={len(cur)} sha256={sha(cur)[:24]}")
        path.write_bytes(cur.replace(orig_bytes, bad_bytes, 1))
        print(f"注入 cmd{cmd_no} 选点 -> {rel} len={len(path.read_bytes())} sha256={sha(path.read_bytes())[:24]}")
        print(f"按 CI 同序预检，预期红点在 cmd{cmd_no}：")
        hit = precheck(cmd_no)
        print(f"预检通过：红点恰在 cmd{hit}，前 {hit - 1} 条全绿")
    else:
        want = stash.read_bytes()
        path.write_bytes(want)
        got = path.read_bytes()
        if sha(got) != sha(want):
            raise SystemExit("还原后字节不一致")
        print(f"还原 {rel} len={len(got)} sha256={sha(got)[:24]}")
        print("按 CI 同序预检，预期全绿：")
        hit = precheck(0)
        if hit != 0:
            raise SystemExit(f"还原后仍红在 cmd{hit}")
        print("预检通过：12 条全绿")


if __name__ == "__main__":
    main()
