#!/usr/bin/env python3
"""Contained, opt-in PATCH coalescing regressions; no device or network access."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import struct
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]
IO = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
CC = Path("D:/install/mingw64/bin/gcc.exe")
SOURCES = [ROOT / path for path in (
    "Libraries/OTA/ota_patch.c", "Libraries/OTA/ota_keys.c",
    "boot/src/boot_crc32.c", "boot/src/boot_sha256.c", "boot/src/boot_fw_header.c",
    "bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c",
    "bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c")]
INCLUDES = [ROOT / path for path in (
    "Libraries", "boot/include", "bsdiff_lzma_AES128-main/bspatch/lzma",
    "bsdiff_lzma_AES128-main/bspatch/AES128_CTR")]
WITNESS_SHA = "131624717d5972039ee76847d4a410fc21edebf9a5b4730d37b9dfe2ab04573e"
OUT: Path
WITNESS: Path | None
ENV: dict[str, str]
PACK: object
BASE: bytes
COMMANDS: list[dict] = []
OBSERVATIONS: list[dict] = []
BINARIES: dict[tuple[str, int], Path] = {}
CASES: dict[str, dict] = {}
REFERENCE: dict[int, dict] = {}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def checked(path):
    return IO["checked_output"](ROOT, path)


def record(path):
    path = Path(path)
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def save(relative, raw):
    path = checked(OUT / relative)
    checked(path.parent).mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)
    return path


def command(tag, args):
    paths = [checked(OUT / "commands" / (tag + suffix))
             for suffix in (".stdout", ".stderr", ".json")]
    require(not any(path.exists() for path in paths), "preserve command evidence: " + tag)
    started = time.monotonic()
    timeout = None
    try:
        proc = subprocess.run(list(map(str, args)), cwd=ROOT, env=ENV,
                              capture_output=True, timeout=120,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as error:
        stdout, stderr, code = error.stdout or b"", error.stderr or b"", None
        timeout = 120
    for path, raw in zip(paths, (stdout, stderr)):
        with path.open("xb") as stream:
            stream.write(raw)
    receipt = dict(args=list(map(str, args)), cwd=str(ROOT), exit=code, timeout=timeout,
                   seconds=time.monotonic() - started, stdout=record(paths[0]),
                   stderr=record(paths[1]), warnings=len(re.findall(rb"\bwarning:", stdout + stderr)),
                   errors=len(re.findall(rb"\berror:", stdout + stderr)))
    IO["write_json"](ROOT, paths[2], receipt)
    COMMANDS.append(receipt)
    require(timeout is None, "host command timed out: " + tag)
    return code, stdout, stderr


def compile_one(name, harness, mode, *, source=None, flags=()):
    exe = checked(OUT / "bin" / (name + ".exe"))
    require(not exe.exists(), "preserve executable")
    args = [CC, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", *flags,
            *["-I" + str(path) for path in INCLUDES]]
    if mode:
        args.append("-DOTA_PATCH_COALESCE_WRITES=1")
    args += [harness, source or SOURCES[0], *SOURCES[1:], "-o", exe]
    code, stdout, stderr = command(name + "-compile", args)
    require(code == 0 and not re.search(rb"\bwarning:", stdout + stderr),
            "compile failed/warned: " + name + "\n" + stderr.decode("utf-8", "replace"))
    return exe


def offtout(value):
    require(-(1 << 63) < value < (1 << 63), "control outside sign-magnitude range")
    return (abs(value) | ((1 << 63) if value < 0 else 0)).to_bytes(8, "little")


def control_bytes(control):
    return b"".join(offtout(value) for value in control)


def patch_stream(target, controls):
    raw = bytearray()
    oldpos = newpos = 0
    for diff, extra, seek in controls:
        require(diff >= 0 and extra >= 0 and newpos + diff + extra <= len(target),
                "invalid generated output extent")
        raw += control_bytes((diff, extra, seek))
        raw += bytes((target[newpos + i] -
                      (BASE[oldpos + i] if 0 <= oldpos + i < len(BASE) else 0)) & 255
                     for i in range(diff))
        newpos += diff
        oldpos += diff
        raw += target[newpos:newpos + extra]
        newpos += extra
        oldpos += seek
    require(newpos == len(target), "generated output is incomplete")
    return bytes(raw)


def target_image(size):
    image = bytearray(hashlib.shake_256(b"P34-INSTALL-03-test-only").digest(size))
    image[0x400:0x460] = PACK.build_fw_header(bytes(image), "2.8.3", 1786320000)
    return bytes(image)


def package_bytes(target, raw, *, compressed=None, declared=None, bad_crc=False,
                  target_vcode=20803):
    alone = PACK.lzma_alone_encode(raw)
    stream = alone[13:] if compressed is None else compressed
    inner = bytearray(40)
    struct.pack_into(">I", inner, 4, len(stream))
    struct.pack_into("<II", inner, 8, len(BASE), len(target))
    struct.pack_into(">II", inner, 16, PACK.crc32(BASE),
                     PACK.crc32(target) ^ int(bad_crc))
    inner[24:29] = alone[:5]
    struct.pack_into("<Q", inner, 32, len(raw) if declared is None else declared)
    struct.pack_into(">I", inner, 0, PACK.crc32(bytes(inner)))
    # Deterministic, test-only nonces. These fixtures must never be distributed.
    nonce = hashlib.sha256(b"coalesce-fixture" + bytes(inner) + stream).digest()[:16]
    payload = PACK.aes_ctr_xcrypt(bytes.fromhex(PACK.DEFAULT_KEY_HEX), nonce,
                                 bytes(inner) + stream, encrypt=True)
    return PACK.build_etu_header(7, nonce, payload, target_vcode, 20700,
                                 hashlib.sha256(BASE).digest()[:8]) + payload


def add_case(name, target, controls, *, raw=None, **options):
    raw = patch_stream(target, controls) if raw is None else raw
    value = dict(package=save("vectors/" + name + ".etu", package_bytes(target, raw, **options)),
                 target=save("vectors/" + name + ".bin", target), size=len(target),
                 controls=controls)
    CASES[name] = value
    return value


def write_lengths(case, mode):
    pieces = ([case["size"]] if mode else
              [n for diff, extra, _ in case["controls"] for n in (diff, extra) if n])
    return [min(1024, n - offset) for n in pieces for offset in range(0, n, 1024)]


def observe(tag, case, mode, expected="ok", fault="none", at=0, *, executable=None,
            expect_oracle_failure=False):
    code, stdout, stderr = command(tag, [executable or BINARIES["oracle", mode],
        case["package"], OUT / "vectors/base.bin", case["target"], expected, fault, at])
    require(code == int(expect_oracle_failure),
            "native oracle exit: " + tag + "\n" + (stdout + stderr).decode("utf-8", "replace"))
    value = json.loads(stdout)
    require(value["coalesce"] == mode and value["passed"] == int(not expect_oracle_failure),
            "missing/mismatched native oracle: " + tag)
    OBSERVATIONS.append(dict(tag=tag, expected=expected, fault=fault, at=at,
                             oracle_failure_expected=expect_oracle_failure, observed=value))
    return value


class PatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for mode in (0, 1):
            for name, harness, flags in (
                ("legacy", ROOT / "tests/ota/test_ota_patch.c", ()),
                ("oracle", ROOT / "tests/ota/test_ota_patch_coalesce.c", ()),
                ("capacity", ROOT / "tests/ota/test_p2_6_capacity_patch.c",
                 ("-DOTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE=1",))):
                BINARIES[name, mode] = compile_one(name + "-" + str(mode), harness, mode, flags=flags)
            if WITNESS:
                BINARIES["reference", mode] = compile_one("reference-" + str(mode),
                    WITNESS / "scripts/patch_host.c", mode)

    def test_existing_public_api_regressions(self):
        for mode in (0, 1):
            with self.subTest(mode=mode):
                code, stdout, stderr = command("legacy-" + str(mode), [BINARIES["legacy", mode]])
                counts = re.findall(rb"(\d+)/(\d+) checks passed", stdout)
                self.assertEqual(code, 0, (stdout + stderr).decode("utf-8", "replace"))
                self.assertEqual(len(counts), 1)
                self.assertEqual(counts[0][0], counts[0][1])
                self.assertGreater(int(counts[0][0]), 0)
                OBSERVATIONS.append(dict(tag="legacy-" + str(mode), checks=int(counts[0][0])))

    def test_diff_extra_control_and_buffer_boundaries(self):
        for name in ["mixed", *[key for key in CASES if key.startswith("boundary-")]]:
            case = CASES[name]
            for mode in (0, 1):
                with self.subTest(case=name, mode=mode):
                    value = observe(name + "-" + str(mode), case, mode)
                    sizes = write_lengths(case, mode)
                    self.assertEqual(value["programs"], len(sizes))
                    self.assertEqual(value["readbacks"], len(sizes))
                    self.assertEqual(value["programmed"], case["size"])
                    self.assertEqual(value["last_write"], sizes[-1])
                    self.assertEqual(value["byte_identical"], 1)

    def test_program_and_readback_failures_stop_without_flush(self):
        case = CASES["mixed"]
        for mode in (0, 1):
            sizes = write_lengths(case, mode)
            for fault, expected in (("program", "candidate_write"), ("readback", "candidate_verify"),
                                    ("corrupt", "candidate_verify")):
                for at in (1, 2, len(sizes)):
                    with self.subTest(mode=mode, fault=fault, at=at):
                        value = observe(f"fault-{mode}-{fault}-{at}", case, mode, expected, fault, at)
                        written = at - int(fault == "program")
                        self.assertEqual(value["programs"], at)
                        self.assertEqual(value["readbacks"], written)
                        self.assertEqual(value["programmed"], sum(sizes[:written]))
                        self.assertEqual(value["final_reads"], 0)

    def test_base_read_failure_discards_pending_bytes(self):
        for mode in (0, 1):
            value = observe("base-fault-" + str(mode), CASES["mixed"], mode, "read", "base", 2)
            self.assertEqual(value["programs"], 0 if mode else 2)
            self.assertEqual(value["programmed"], 0 if mode else 42)
            self.assertEqual(value["final_reads"], 0)

    def test_second_pass_package_read_failure(self):
        case = CASES["boundary-extra-8193"]
        for mode in (0, 1):
            value = observe("stream-read-fault-" + str(mode), case, mode, "read", "package", 1)
            self.assertGreater(value["programmed"], 0)
            self.assertLess(value["programmed"], case["size"])
            self.assertEqual(value["programmed"] % 1024, 0)
            self.assertEqual(value["final_reads"], 0)

    def test_bad_controls_never_flush_pending_tail(self):
        for name, default_bytes, enabled_bytes in (
            ("control-short", 513, 0), ("control-after-full", 1025, 1024),
            ("negative-diff", 513, 0), ("extra-overflow", 513, 0),
            ("oldpos-overflow", 513, 0), ("final-seek-overflow", 2051, 2048),
            ("unconsumed-control", 2051, 2048)):
            for mode in (0, 1):
                with self.subTest(case=name, mode=mode):
                    value = observe(name + "-" + str(mode), CASES[name], mode, "patch_control")
                    self.assertEqual(value["programmed"], enabled_bytes if mode else default_bytes)
                    self.assertEqual(value["final_reads"], 0)

    def test_stream_rejections_precede_candidate_prepare(self):
        for name, expected in (("truncated", "lzma_data"), ("compressed-tail", "lzma_data"),
                               ("decoded-excess", "decoded_length")):
            for mode in (0, 1):
                with self.subTest(case=name, mode=mode):
                    value = observe(name + "-" + str(mode), CASES[name], mode, expected)
                    self.assertEqual(value["prepares"], 0)
                    self.assertEqual(value["programs"], 0)

    def test_full_image_integrity_gates_still_run_after_tail(self):
        for name, expected in (("bad-crc", "result_crc"), ("bad-fw", "fw_header"),
                               ("bad-target-version", "image_metadata")):
            for mode in (0, 1):
                with self.subTest(case=name, mode=mode):
                    value = observe(name + "-" + str(mode), CASES[name], mode, expected)
                    self.assertEqual(value["programmed"], CASES[name]["size"])
                    self.assertEqual(value["programs"], len(write_lengths(CASES[name], mode)))
                    self.assertGreater(value["final_reads"], 0)
        for mode in (0, 1):
            value = observe("final-read-fault-" + str(mode), CASES["mixed"], mode,
                            "read", "final-read", 1)
            self.assertEqual(value["programmed"], CASES["mixed"]["size"])

    def test_exact_workspace_capacity_and_one_byte_short(self):
        for mode in (0, 1):
            code, stdout, stderr = command("capacity-" + str(mode), [BINARIES["capacity", mode]])
            self.assertEqual(code, 0, (stdout + stderr).decode("utf-8", "replace"))
            self.assertEqual(stdout.count(b"status=PASS"), 2)
            self.assertIn(b"candidate_prepares=0 candidate_programs=0 status=PASS", stdout)

    def test_original_1mib_witness_same_bytes_both_modes(self):
        if not WITNESS:
            self.skipTest("original witness was not supplied; no 1 MiB claim")
        for mode in (0, 1):
            code, stdout, stderr = command("witness-" + str(mode), [BINARIES["reference", mode],
                WITNESS / "cases/reference-1MiB.etu", WITNESS / "cases/base.bin",
                WITNESS / "cases/target.bin", "ok"])
            self.assertEqual(code, 0, (stdout + stderr).decode("utf-8", "replace"))
            value = json.loads(stdout)
            for field in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok"):
                self.assertIs(value[field], True)
            self.assertEqual(value["package_bytes"], 1048576)
            self.assertEqual(value["programmed_bytes"], 603764)
            self.assertEqual(value["program_calls"], 590 if mode else 212679)
            self.assertEqual(value["max_write"], 1024)
            self.assertLessEqual(value["workspace_peak"], 40960)
            REFERENCE[mode] = value
        self.assertLessEqual(REFERENCE[1]["workspace_peak"] - REFERENCE[0]["workspace_peak"], 8)

    def test_runtime_oracles_reject_two_broken_coalescers(self):
        source = SOURCES[0].read_text(encoding="utf-8")
        for name, old, new in (
            ("short-flush", "if (state->candidate_buffered == sizeof(state->work))",
             "if (state->candidate_buffered != 0u)"),
            ("drop-tail", "if (state->candidate_buffered != 0u)\n    {\n        return flush_candidate_buffer",
             "if (state->candidate_buffered == 0u)\n    {\n        return flush_candidate_buffer")):
            with self.subTest(mutation=name):
                self.assertEqual(source.count(old), 1)
                path = save("mutants/" + name + ".c", source.replace(old, new, 1).encode("utf-8"))
                exe = compile_one("mutant-" + name, ROOT / "tests/ota/test_ota_patch_coalesce.c",
                                  1, source=path)
                observe("mutant-" + name, CASES["mixed"], 1, executable=exe, expect_oracle_failure=True)

    def test_output_guard_rejects_sibling_without_writing(self):
        with self.assertRaises(IO["OutputBoundaryError"]):
            checked(ROOT.parent / (ROOT.name + "-coalesce-not-authorized") / "result.json")


def prepare_vectors():
    save("vectors/base.bin", BASE)
    for size in (1120, 2047, 2048, 2049, 3071, 3072, 3073, 8193):
        target = target_image(size)
        add_case("boundary-diff-" + str(size), target, [(size, 0, 0)])
        add_case("boundary-extra-" + str(size), target, [(0, size, 0)])
    target = target_image(2051)
    mixed = [(13, 29, 77), (700, 1, -820), (200, 501, 5000), (607, 0, 0)]
    add_case("mixed", target, mixed)
    for name, prefix in (("control-short", 513), ("control-after-full", 1025)):
        add_case(name, target, [(prefix, 0, 0), (0, 0, 0), (0, len(target) - prefix, 0)])
    controls = [(513, 0, 0), (len(target) - 513, 0, 0)]
    raw = patch_stream(target, controls)
    for name, bad in (("negative-diff", (-1, 0, 0)), ("extra-overflow", (0, len(target), 0))):
        add_case(name, target, controls,
                 raw=raw[:537] + control_bytes(bad) + raw[561:])
    add_case("oldpos-overflow", target, [(513, 0, (1 << 63) - 1 - 513), (1538, 0, 0)])
    add_case("final-seek-overflow", target, [(13, 0, (1 << 63) - 1 - 13), (0, 2038, 1)])
    controls = [(len(target), 0, 0)]
    raw = patch_stream(target, controls)
    add_case("unconsumed-control", target, controls, raw=raw + control_bytes((0, 0, 1)))
    compressed = PACK.lzma_alone_encode(raw)[13:]
    add_case("truncated", target, controls, compressed=compressed[:-1])
    add_case("compressed-tail", target, controls, compressed=compressed + b"\0")
    add_case("decoded-excess", target, controls, raw=raw + b"\0", declared=len(raw))
    add_case("bad-crc", target, mixed, bad_crc=True)
    corrupt = bytearray(target)
    corrupt[0x400] ^= 1
    add_case("bad-fw", bytes(corrupt), mixed)
    add_case("bad-target-version", target, mixed, target_vcode=20804)
    IO["write_json"](ROOT, OUT / "vectors.json", {name: dict(
        package=record(value["package"]), target=record(value["target"]),
        controls=value["controls"], size=value["size"]) for name, value in CASES.items()})


def main():
    global OUT, WITNESS, ENV, PACK, BASE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--witness-dir")
    args = parser.parse_args()
    require(Path(args.root) == ROOT and Path.cwd() == ROOT and sys.flags.isolated and
            sys.flags.no_site and sys.dont_write_bytecode, "explicit isolated project root required")
    OUT = checked(args.out)
    require(OUT.is_relative_to(ROOT / ".cache") and not OUT.exists(), "fresh project .cache output required")
    WITNESS = Path(args.witness_dir).resolve(strict=True) if args.witness_dir else None
    inputs = set(SOURCES + [Path(__file__), ROOT / "Tools/etu_pack.py", ROOT / "Tools/etu_unpack.py",
        ROOT / "tests/ota/test_ota_patch.c", ROOT / "tests/ota/test_ota_patch_coalesce.c",
        ROOT / "tests/ota/test_p2_6_capacity_patch.c",
        ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"])
    for folder in [ROOT / "Libraries/OTA", *INCLUDES[1:]]:
        inputs.update(folder.glob("*.h"))
    inputs.update((ROOT / "tests/ota-vectors").glob("toy-*.bin"))
    inputs.update(ROOT / "tests/ota-vectors" / name for name in (
        "toy-patch.etu", "p2-3-vendor-oldpos.etu", "p2-3-vendor-oldpos-new.bin", "p2-3-invalid-control.etu"))
    if WITNESS:
        witness = json.loads((WITNESS / "proof/witness.json").read_text(encoding="utf-8"))
        require(witness["etu_sha256"] == WITNESS_SHA, "wrong original witness")
        for relative, field in (("cases/reference-1MiB.etu", "etu_sha256"), ("cases/base.bin", "base_sha256"),
                                ("cases/target.bin", "target_sha256"), ("cases/reference.raw-patch", "raw_sha256")):
            path = WITNESS / relative
            require(record(path)["sha256"] == witness[field], "original witness bytes changed: " + relative)
            inputs.add(path)
        inputs.update(WITNESS / path for path in (
            "scripts/patch_host.c", "proof/witness.json", "proof/build-v1.json", "proof/validation-r1.json"))
    before = [record(path) for path in sorted(inputs)]
    environment_paths = {name: checked(OUT / "host" / folder) for name, folder in {
        "HOME": "home", "USERPROFILE": "home", "APPDATA": "appdata", "LOCALAPPDATA": "localappdata",
        "TEMP": "tmp", "TMP": "tmp", "TMPDIR": "tmp", "XDG_CACHE_HOME": "cache",
        "XDG_CONFIG_HOME": "config", "XDG_DATA_HOME": "data", "XDG_STATE_HOME": "state",
        "PYTHONUSERBASE": "python", "PYTHONPYCACHEPREFIX": "pycache"}.items()}
    for name in ("intent.json", "result.json", "unittest.log", "vectors.json", "outputs.json"):
        checked(OUT / name)
    require(CC.is_file(), "host GCC missing")
    checked(OUT.parent).mkdir(parents=True, exist_ok=True)
    OUT.mkdir()
    for folder in ("bin", "commands", "vectors", "mutants"):
        checked(OUT / folder).mkdir()
    ENV = dict(os.environ)
    for name, path in environment_paths.items():
        path.mkdir(parents=True, exist_ok=True)
        ENV[name] = str(path)
    for name in ("CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH", "COMPILER_PATH",
                 "GCC_EXEC_PREFIX", "GCC_COMPARE_DEBUG", "GCOV_ERROR_FILE", "LLVM_PROFILE_FILE"):
        ENV.pop(name, None)
    ENV.update(PATH=str(CC.parent) + os.pathsep + str(Path(os.environ["SystemRoot"]) / "System32"),
               PYTHONDONTWRITEBYTECODE="1", CCACHE_DISABLE="1", SCCACHE_DISABLE="1", SOURCE_DATE_EPOCH="1786320000")
    os.environ.update(ENV)
    IO["write_json"](ROOT, OUT / "intent.json", dict(inputs=before, compiler=record(CC),
        outputs_root=str(OUT), environment={name: str(path) for name, path in environment_paths.items()},
        hardware=False, physical_timing=False, independent_acceptance=False))
    # Load installed Crypto read-only; -I/-S/-B and contained caches remain in force.
    sys.path.insert(0, str(Path(sys.executable).parent / "Lib/site-packages"))
    sys.path.insert(0, str(ROOT / "Tools"))
    import etu_pack
    PACK = etu_pack
    BASE = (ROOT / "tests/ota-vectors/toy-old.bin").read_bytes()
    prepare_vectors()
    with (OUT / "unittest.log").open("x", encoding="utf-8", newline="\n") as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(PatchTests))
    unchanged = before == [record(path) for path in sorted(inputs)]
    output_paths = [checked(path) for path in sorted(OUT.rglob("*"))]
    IO["write_json"](ROOT, OUT / "outputs.json", dict(root=str(ROOT),
        paths=[str(path) for path in output_paths], files=[record(path) for path in output_paths if path.is_file()],
        environment={name: str(path) for name, path in environment_paths.items()}))
    value = dict(result="HOST_PASS" if result.wasSuccessful() and unchanged else "HOST_FAIL",
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped),
        inputs_unchanged=unchanged, inputs=before, commands=COMMANDS, observations=OBSERVATIONS,
        reference=REFERENCE, binaries=[record(path) for path in BINARIES.values()], log=record(OUT / "unittest.log"),
        audit=record(OUT / "outputs.json"), hardware=False, physical_timing=False, independent_acceptance=False)
    IO["write_json"](ROOT, OUT / "result.json", value)
    print(json.dumps({key: value[key] for key in ("result", "tests", "failures", "errors", "skipped")}),
          str(OUT / "result.json"), flush=True)
    if not result.wasSuccessful() or not unchanged:
        print((OUT / "unittest.log").read_text(encoding="utf-8")[-16000:])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
