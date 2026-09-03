#!/usr/bin/env python3
"""P3-7: 按 CI 同序在本地跑 12 条 host 测试命令,报告每条退出码。"""
import subprocess, sys
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
stop = False
for i, c in enumerate(CMDS, 1):
    r = subprocess.run([sys.executable, "-X", "utf8", "-B", c],
                       capture_output=True, text=True)
    tag = "GREEN" if r.returncode == 0 else "RED"
    print(f"cmd{i:2d} [{tag}] rc={r.returncode}  {c}")
    if r.returncode != 0:
        tail = (r.stdout + r.stderr).strip().splitlines()
        for ln in tail[-3:]:
            print(f"      | {ln}")
        stop = True
        break
sys.exit(1 if stop else 0)
