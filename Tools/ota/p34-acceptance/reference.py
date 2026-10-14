"""Prepare a legal 1 MiB fixture with the existing encoder and real C decoder."""
import argparse
import contextlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import shutil
import struct
import sys
import sysconfig
import types
import zlib

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("p34_reference_build", HERE / "build.py")
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
ROOT = host.ROOT


def encode_fast(data, dict_size=16384):
    filters = [dict(id=lzma.FILTER_LZMA1, dict_size=dict_size, lc=2, lp=0, pb=0,
                    mode=lzma.MODE_FAST, nice_len=32, mf=lzma.MF_HC3, depth=8)]
    encoder = lzma.LZMACompressor(format=lzma.FORMAT_ALONE, filters=filters)
    blob = encoder.compress(data) + encoder.flush()
    return blob[:5] + struct.pack("<Q", len(data)) + blob[13:]


def header_mutation(blob, offset, value):
    changed = bytearray(blob)
    changed[offset:offset + len(value)] = value
    struct.pack_into("<I", changed, 60, zlib.crc32(changed[:60]) & 0xffffffff)
    return bytes(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cc", default="gcc")
    parser.add_argument("--base-version", default="3.2.86-p34a")
    parser.add_argument("--target-version", default="3.2.87-p34a")
    args = parser.parse_args()
    if Path.cwd() != ROOT or not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("explicit worktree and isolated Python required")
    if os.environ.get("OTA_AES_KEY"):
        raise RuntimeError("reference fixtures use only the existing development key policy")
    source = args.app.resolve(strict=True)
    out = host.checked(args.out)
    if out.exists():
        raise RuntimeError("preserve earlier fixture generation")
    for leaf in ("base.bin", "target.bin", "reference.exe", "reference", "search.log", "logs", "proof", "cases",
                 "intent.json", "result.json", "failed.json"):
        host.checked(out / leaf)
    for label in ("compiler", "compile", "positive", "payload-crc", "truncated", "same-version", "wrong-base-sha"):
        for ext in (".log", ".json", ".etu"):
            host.checked(out / (label + ext))
    env = host.environment(out)
    os.environ.update(env)
    sys.path[:0] = [str(ROOT / "Tools"), sysconfig.get_path("platlib"), sysconfig.get_path("purelib")]
    pack = host.load("p34_reference_pack", ROOT / "Tools/etu_pack.py")
    unpack = host.load("p34_reference_unpack", ROOT / "Tools/etu_unpack.py")
    encoding = host.load("p34_reference_encoding", HERE / "encoding.py")
    encoding.pack = types.SimpleNamespace(**dict(vars(pack), lzma_alone_encode=encode_fast))
    encoding.unpack, encoding.OUT = unpack, out

    def save(relative, data):
        path = host.checked(out / relative)
        host.checked(path.parent).mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        return path

    encoding.save = save
    encoding.save_json = lambda relative, value: host.io.write_json(ROOT, out / relative, value)
    host.io.write_json(ROOT, out / "intent.json", dict(app=host.record(source),
        base_version=args.base_version, target_version=args.target_version,
        encoder="existing FAST/HC3 depth8 16KiB lc2/lp0/pb0", search_budget=128, device_operations=0))
    try:
        raw = source.read_bytes()
        images = []
        for label, version in (("base", args.base_version), ("target", args.target_version)):
            image = bytearray(raw)
            image[0x400:0x460] = pack.build_fw_header(bytes(image), version, 1786320000)
            image = bytes(image)
            unpack.verify_fw_header(image, label)
            if image[:0x400] + image[0x460:] != raw[:0x400] + raw[0x460:]:
                raise RuntimeError("finalizer changed executable bytes")
            images.append(image)
            save(label + ".bin", image)
        base, target = images
        base_version = struct.unpack_from("<I", base, 0x408)[0]
        target_version = struct.unpack_from("<I", target, 0x408)[0]
        if target_version <= base_version:
            raise RuntimeError("reference target must be a newer legal version")
        with (out / "search.log").open("x", encoding="utf-8") as log, contextlib.redirect_stdout(log):
            selection = encoding.search(base, target, seed=1931, budget=128)
            encoding.save_json("proof/selection.json", selection)
            encoding.witness(base, target, selection)
        package = out / "cases/reference-1MiB.etu"
        blob = package.read_bytes()
        if len(blob) != 1048576:
            raise RuntimeError("reference is not exactly 1 MiB")
        header = unpack.parse_etu_header(blob)
        if header["target_vcode"] != target_version or header["base_vcode"] != base_version:
            raise RuntimeError("reference image versions differ")
        cc = shutil.which(args.cc, path=env.get("PATH"))
        if cc is None:
            raise RuntimeError("native C compiler unavailable")
        exe = out / ("reference.exe" if os.name == "nt" else "reference")
        host.run(out, env, "compiler", [cc, "--version"], 30)
        sources = [HERE / "reference_host.c"] + [ROOT / path for path in (
            "Libraries/OTA/ota_patch.c", "Libraries/OTA/ota_keys.c", "boot/src/boot_crc32.c",
            "boot/src/boot_sha256.c", "boot/src/boot_fw_header.c",
            "bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c", "bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c")]
        includes = [ROOT / path for path in ("Libraries", "boot/include",
                    "bsdiff_lzma_AES128-main/bspatch/lzma", "bsdiff_lzma_AES128-main/bspatch/AES128_CTR")]
        log = host.run(out, env, "compile", [cc, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
            "-DOTA_PATCH_COALESCE_WRITES=1", "-DCONFIG_OTA_APP_CRC32_NIBBLE=1",
            *["-I" + str(path) for path in includes], *sources, "-o", exe], 90)
        if log:
            raise RuntimeError("unexpected native compile diagnostics; inspect compile.log")

        def verify(label, path, expected):
            value = json.loads(host.run(out, env, label, [exe, path, out / "base.bin", out / "target.bin", expected], 90))
            if value["passed"] is not True or value["result"] != expected:
                raise RuntimeError("native decoder result mismatch")
            if expected == "ok":
                if not all(value[name] is True for name in ("byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")):
                    raise RuntimeError("native integrity or workspace check failed")
            elif value["prepares"] != 0:
                raise RuntimeError("invalid input reached candidate preparation")
            return value

        positive = verify("positive", package, "ok")
        corrupted = bytearray(blob)
        corrupted[-1] ^= 1
        negatives = []
        for label, data, expected in (
            ("payload-crc", bytes(corrupted), "payload_crc"),
            ("truncated", blob[:-1], "package_length"),
            ("same-version", header_mutation(blob, 40, struct.pack("<I", base_version)), "version"),
            ("wrong-base-sha", header_mutation(blob, 52, bytes([blob[52] ^ 1])), "base_sha8"),
        ):
            path = save(label + ".etu", data)
            negatives.append(dict(case=label, result=verify(label, path, expected)))
        result = dict(result="LEGAL_1MIB_REFERENCE_READY", base=host.record(out / "base.bin"),
            target=host.record(out / "target.bin"), package=host.record(package),
            base_version=base_version, target_version=target_version, decoder=host.record(exe),
            selection=selection, positive=positive, negatives=negatives,
            sources=[host.record(path) for path in [Path(__file__), HERE / "build.py", HERE / "encoding.py", *sources]],
            installed=False, equivalent_initial_state_qualified=False, formal_freeze=False, independent_acceptance=False)
        host.io.write_json(ROOT, out / "result.json", result)
        print("LEGAL_1MIB_REFERENCE_READY native_positive=1 negatives=4", flush=True)
    except Exception as error:
        host.io.write_json(ROOT, out / "failed.json", dict(error=str(error), preserve_outputs=True, device_operations=0))
        raise


if __name__ == "__main__":
    main()
