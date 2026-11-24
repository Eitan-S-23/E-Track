"""Compile the real MCU frame decoder, then test planned batches and corruption."""
import argparse
import binascii
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    io = load("io_guard", ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py")
    batch = load("batch_plan", ROOT / "Tools/ota/p34_batch_plan.py")
    out = io.checked_output(ROOT, args.out)
    assert not out.exists(), "preserve test output"
    outputs = [out / leaf for leaf in ("host", "decoder.exe", "compile.log", "result.json")]
    for path in outputs:
        io.checked_output(ROOT, path)
    cc = shutil.which("gcc")
    if not cc:
        raise RuntimeError("GCC host compiler required; no local Flutter build")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GCC_")}
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR"):
        path = io.checked_output(ROOT, out / "host" / name.lower())
        path.mkdir(parents=True)
        env[name] = str(path)
    command = [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
               "-I" + str(ROOT / "Libraries"), str(ROOT / "tests/ota/p34_batch_wire.c"),
               str(ROOT / "Libraries/OTA/ota_ble_frame.c"), "-o", str(out / "decoder.exe")]
    compiled = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=60)
    (out / "compile.log").write_bytes(compiled.stdout + compiled.stderr)
    if compiled.returncode:
        raise RuntimeError("native decoder build failed; inspect compile.log")
    frames = []
    for i in range(3):
        payload = struct.pack("<I", i * 128) + bytes((x + i) % 256 for x in range(128))
        body = struct.pack("<BBHH", 2, 7, i + 1, len(payload)) + payload
        frames.append(b"\xa5\x5a" + body + struct.pack("<H", binascii.crc_hqx(body, 0xffff)))
    cases = []
    for mtu in (20, 142, 244, 512):
        plan = batch.plan_batch(frames, [0, 128, 256], chunk_bytes=mtu, credit=28, maximum_frames=3)
        wire = b"".join(plan["chunks"])
        cases.append(("valid_mtu_" + str(mtu), wire, True))
    original = b"".join(frames)
    damaged = bytearray(original)
    damaged[200] ^= 1
    cases.extend([("crc_damage", bytes(damaged), False),
                  ("truncated_final_frame", original[:-1], False),
                  ("missing_middle_frame", frames[0] + frames[2], False),
                  ("reordered_frames", frames[1] + frames[0] + frames[2], False)])
    results = []
    for name, data, expected in cases:
        result = subprocess.run([str(out / "decoder.exe")], input=data, cwd=ROOT,
                                env=env, capture_output=True, timeout=10)
        results.append(dict(name=name, exit=result.returncode, passed=(result.returncode == 0) == expected))
    passed = all(row["passed"] for row in results)
    io.write_json(ROOT, out / "result.json", dict(result="PASS" if passed else "FAIL",
        tests=results, compiler_exit=compiled.returncode, compile_diagnostics_bytes=len(compiled.stdout + compiled.stderr),
        device_operations=0, scope="real frame decoder only; not ACK, cancellation or BLE runtime acceptance"))
    print(json.dumps(dict(result="PASS" if passed else "FAIL", tests=results)))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
