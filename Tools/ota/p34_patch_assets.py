"""Write-once host assets for the prepared PATCH-coalescing receiver."""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import secrets
import struct
import sys
import time
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_patch_preparation as prep

ROOT, OUT = prep.ROOT, prep.AREA / "assets"
FIRMWARE = prep.AREA / "firmware"
PROOF = ROOT / ".cache/p3-4-size-check-20260920/scripts/size_proof.py"
BSDIFF = ROOT / "bsdiff_lzma_AES128-main/bsdiff/build/bin/bsdiff.exe"
RESULT = "PATCH_ASSETS_HOST_VERIFIED"
SEARCH_BUDGET = 128
RELATIVE = ".cache/p34-patch-next/assets/result.json"
BUILD_REPORT = ".cache/p34-patch-next/firmware/build.json"
EXPECTED_BUILD_RESULT = "PATCH_APP_BUILD_PASS"
EXPECTED_BUILD_FEATURE = "coalesce"
EXTRA_INPUTS = ()


def pure_functions(path, names, namespace):
    """Reuse inspected functions without importing device/bootstrap side effects."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    prep.require({node.name for node in functions} == set(names), "required helper definitions changed")
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace


def environment():
    before = prep.common.AREA
    try:
        prep.common.AREA = OUT
        return prep.common.environment()
    finally:
        prep.common.AREA = before


def run(tag, args, env, *, cwd=OUT):
    before = prep.common.AREA
    try:
        prep.common.AREA = OUT
        return prep.common.run(tag, args, cwd, env, 180)
    finally:
        prep.common.AREA = before


def packers():
    prep.require(not os.environ.get("OTA_AES_KEY"), "external packaging-key override rejected")
    sys.path.insert(0, str(Path(sys.executable).parent / "Lib/site-packages"))
    return (prep.load("p34_patch_frozen_pack", prep.FW / "Tools/etu_pack.py"),
            prep.load("p34_patch_frozen_unpack", prep.FW / "Tools/etu_unpack.py"))


def identity(image, unpack):
    unpack.verify_fw_header(image, "P34-INSTALL-03")
    header = image[0x400:0x460]
    return dict(version_code=struct.unpack_from("<I", header, 8)[0],
        version_name=header[12:28].split(b"\0", 1)[0].decode("ascii"), image_len=len(image),
        raw_image_sha256=hashlib.sha256(image).hexdigest(),
        build_timestamp=struct.unpack_from("<I", header, 28)[0],
        hardware_rev=struct.unpack_from("<I", header, 32)[0], layout_id=header[72],
        min_boot=header[73], integrity_sha256=header[40:72].hex())


def wrap_payload(pack, plaintext, base, target, *, kind):
    prep.require(kind in ("full", "patch"), "unknown package kind")
    nonce = secrets.token_bytes(16)
    payload = pack.aes_ctr_xcrypt(bytes.fromhex(pack.DEFAULT_KEY_HEX), nonce, plaintext, True)
    target_vcode = struct.unpack_from("<I", target, 0x408)[0]
    base_vcode = struct.unpack_from("<I", base, 0x408)[0] if kind == "patch" else 0
    base_sha8 = hashlib.sha256(base).digest()[:8] if kind == "patch" else bytes(8)
    header = pack.build_etu_header(7 if kind == "patch" else 11, nonce, payload,
                                   target_vcode, base_vcode, base_sha8)
    pack.check_limits(len(target), len(header) + len(payload), "p34-patch-preparation")
    return header + payload


def package_header(blob, kind, receiver, target, base_sha256, unpack):
    prep.require(kind in ("full", "patch") and type(receiver) is int and type(target) is int and
                 0 < receiver < target <= 0xffffffff, "invalid package identity/kind")
    outer = unpack.parse_etu_header(blob)
    flags, algorithm, key_id = struct.unpack_from("<HII", blob, 6)
    base_vcode = struct.unpack_from("<I", blob, 44)[0]
    expected_base = bytes.fromhex(base_sha256)[:8] if kind == "patch" else bytes(8)
    prep.require(flags == (7 if kind == "patch" else 11) and algorithm == key_id == 1,
                 "package flags/algorithm/key changed")
    prep.require(outer["target_vcode"] == target and base_vcode == (receiver if kind == "patch" else 0)
                 and blob[52:60] == expected_base, "package target/base identity changed")
    prep.require(struct.unpack_from("<H", blob, 48)[0] == 1 and blob[50:52] == b"\1\1",
                 "package hardware/layout/Boot changed")
    return dict(kind=kind, package_bytes=len(blob), payload_bytes=len(outer["payload"]),
                target_vcode=target, base_vcode=base_vcode, base_sha8=blob[52:60].hex(),
                asset_sha256=hashlib.sha256(blob).hexdigest())


def decode_python(blob, base, target, kind, unpack):
    outer = unpack.parse_etu_header(blob)
    plain = unpack.aesctr(bytes.fromhex(unpack.DEFAULT_KEY_HEX), outer["nonce"], outer["payload"], False)
    if kind == "full":
        props, expected, compressed = plain[:5], struct.unpack_from("<Q", plain, 5)[0], plain[13:]
    else:
        inner = unpack.parse_patch_header(plain[:40])
        props, expected, compressed = inner["props"], inner["ph_orig"], plain[40:]
        prep.require(inner["ph_psize"] == len(compressed) and inner["ph_osize"] == len(base) and
                     inner["ph_nsize"] == len(target), "PATCH inner sizes differ")
    prep.require(props[0] == 2 and 4096 <= int.from_bytes(props[1:], "little") <= 16384,
                 "LZMA properties differ from the frozen decoder contract")
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[dict(
        id=lzma.FILTER_LZMA1, dict_size=int.from_bytes(props[1:], "little"), lc=2, lp=0, pb=0)])
    decoded = decoder.decompress(compressed, max_length=expected + 1)
    prep.require(len(decoded) == expected and decoder.eof and not decoder.unused_data,
                 "stream length/EOS/full consumption failed")
    if kind == "patch":
        decoded = unpack.bspatch_apply(base, len(target), decoded)
    prep.require(decoded == target, "Python decoded target differs")
    unpack.verify_fw_header(decoded, "decoded candidate")
    return decoded


def map_object(text, section, name, length, source_leaf):
    entries = re.findall(r"^\s*\." + re.escape(section + "." + name) +
                         r"\s*\n\s*(0x[0-9a-fA-F]+)\s+(0x[0-9a-fA-F]+)\s+([^\n]+)$", text, re.M)
    prep.require(len(entries) == 1, "missing/ambiguous MAP object: " + name)
    address, size, owner = entries[0]
    prep.require(int(size, 16) == length and source_leaf in owner and "X_Track_App_GCC.dir" in owner,
                 "MAP object type/owner differs: " + name)
    return int(address, 16)


def bindings(y, image, image_identity, artifacts, constants):
    original = y["target_bindings"]
    namespace = pure_functions(ROOT / "Tools/ota/baud_mcu.py", ("map_symbol", "map_bss"),
        dict(re=re, b=types.SimpleNamespace(require=prep.require)))
    maps = types.SimpleNamespace(**{name: namespace[name] for name in ("map_symbol", "map_bss")},
        c=types.SimpleNamespace(APP=constants["OTA_APP_ORIGIN"]),
        epoch=types.SimpleNamespace(SYSTICK_RELOAD=original["profile"]["symbols"]["systick_reload"]))
    derive = prep.load("p34_patch_binding_derivation", ROOT / ".cache/p34-next/n03_bindings.py").derive
    symbols = derive(maps, artifacts[".map"]["path"], image["path"], 336)
    result = copy.deepcopy(original)
    raw_image = Path(image["path"]).read_bytes()
    result["profile"].update(image=image, identity=image_identity, map=artifacts[".map"],
        elf=artifacts[".elf"], prefix=raw_image[:0x460].hex(), symbols=symbols)
    text = Path(artifacts[".map"]["path"]).read_text(encoding="utf-8")
    result["layout"]["session"] = maps.map_bss(text, "_ZL13s_ble_session", result["layout"]["members"]["size"])
    for key, name in (("bcb_state", "_ZL20g_ota_state_snapshot"), ("confirm_done", "_ZL18g_ota_confirm_done"),
                      ("state_snapped", "_ZL19g_ota_state_snapped")):
        result["layout"][key] = maps.map_bss(text, name, 1)
    result["flash_admission_addresses"] = dict(
        disabled=map_object(text, "data", "_ZL19g_qspi_ota_disabled", 1, "HAL_W25Q128.cpp"),
        jedec=map_object(text, "bss", "_ZL15g_qspi_jedec_id", 4, "HAL_W25Q128.cpp"),
        boot_clock_ok=map_object(text, "bss", "_ZL14s_p34_clock_ok", 4, "HAL_Bluetooth.cpp"))
    return result


def size_proof(pack, unpack):
    area = OUT / "pressure"
    def save_bytes(relative, data):
        path = area / relative
        prep.raw(path, data)
        return path
    namespace = dict(ROOT=ROOT, OUT=area, TARGET=1048576, pack=pack, unpack=unpack,
                     hashlib=hashlib, json=json, lzma=lzma, secrets=secrets, struct=struct,
                     Path=Path, time=time, save=save_bytes,
                     save_json=lambda relative, value: prep.save(area / relative, value))
    return pure_functions(PROOF, ("digest", "strict_lzma", "signed_offset", "patch_stream", "encode",
                                  "measurement", "search", "package_bytes", "witness"), namespace)


def header_mutation(blob, offset, value):
    changed = bytearray(blob)
    changed[offset:offset + len(value)] = value
    import zlib
    struct.pack_into("<I", changed, 60, zlib.crc32(changed[:60]) & 0xffffffff)
    return bytes(changed)


def native_verify(label, package, base, target, expected, decoder, env):
    value = json.loads(run(label, [decoder["path"], package["path"], base["path"], target["path"], expected], env))
    prep.require(value["passed"] is True and value["result"] == expected, "native package oracle failed")
    if expected == "ok":
        prep.require(all(value[name] is True for name in ("byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")),
                     "native success is missing integrity/lifecycle evidence")
    return value


def decoder_equivalence(host):
    prep.verify_records(host["inputs"] + host["binaries"])
    records = []
    for item in host["inputs"]:
        path = Path(item["path"])
        if not path.is_relative_to(ROOT) or path.relative_to(ROOT).parts[0] not in (
                "Libraries", "boot", "bsdiff_lzma_AES128-main"):
            continue
        candidate = prep.FW / path.relative_to(ROOT)
        prep.require(candidate.is_file(), "native decoder source missing from candidate: " + str(path))
        before, after = prep.historical.resolve(item).read_bytes(), candidate.read_bytes()
        normalized = before.replace(b"\r\n", b"\n")
        prep.require(normalized == after.replace(b"\r\n", b"\n"),
                     "native decoder source differs from candidate: " + str(path))
        records.append(dict(native_input=item, candidate=prep.record(candidate),
            comparison="exact" if before == after else "CRLF/LF-only",
            normalized_sha256=hashlib.sha256(normalized).hexdigest()))
    prep.require(records, "native decoder source provenance is empty")
    return records


def load():
    value = prep.read(OUT / "result.json")
    prep.require(value["result"] == RESULT and value["hardware"] is False and value["independent_acceptance"] is False,
                 "assets were not host-validated")
    prep.verify_records(value["inputs"] + value["outputs"])
    validate_manifest(value)
    return value


def validate_manifest(value):
    prep.require(set(value["groups"]) == {"bootstrap", "compact", "pressure"} and
                 set(value["images"]) == {"aa", "ab"} and value["formal_reference_admitted"] is False,
                 "asset set or formal-admission status changed")
    prep.require(value["decoder_equivalence"] == decoder_equivalence(prep.read(prep.HOST_TESTS)),
                 "native decoder source provenance changed")
    _, unpack = packers()
    build = prep.read(FIRMWARE / "build.json")
    artifacts = {Path(item["path"]).suffix: {key: item[key] for key in ("path", "bytes", "sha256")}
                 for item in build["artifacts"]}
    y = prep.read(prep.Y_ASSETS)
    prep.require(value["historical_receiver"] == y["target"] and
                 value["historical_receiver_bindings"] == y["target_bindings"], "historical Y binding changed")
    for label, version in (("aa", prep.AA), ("ab", prep.AB)):
        item = value["images"][label]
        actual = identity(Path(item["image"]["path"]).read_bytes(), unpack)
        prep.require(item["identity"] == actual and actual["version_code"] == version and
                     item["bindings"] == bindings(y, item["image"], actual, artifacts, build["layout"]["constants"]),
                     "target image/derived binding changed")
    aa, ab = (Path(value["images"][label]["image"]["path"]).read_bytes() for label in ("aa", "ab"))
    prep.require(aa[:0x400] + aa[0x460:] == ab[:0x400] + ab[0x460:], "successor executable differs")
    for name, group in value["groups"].items():
        bootstrap = name == "bootstrap"
        base = y["target"] if bootstrap else value["images"]["aa"]["image"]
        target = value["images"]["aa" if bootstrap else "ab"]["image"]
        kind, receiver, target_version = ("full", y["target_identity"]["version_code"], prep.AA) if bootstrap else ("patch", prep.AA, prep.AB)
        prep.require(group["base"] == base and group["target"] == target and group["kind"] == kind and
                     group["receiver"] == receiver and group["target_version"] == target_version,
                     "package group identity changed")
        prep.verify_records([group["package"], group["base"], group["target"], group["decoded"]])
        blob = Path(group["package"]["path"]).read_bytes()
        prep.require(group["header"] == package_header(blob, kind, receiver, target_version, base["sha256"], unpack),
                     "package header binding changed")
        prep.require(group["native"] == prep.read(OUT / "logs" / (name + "-native.stdout")) and
                     group["native"]["passed"] is True and Path(group["decoded"]["path"]).read_bytes() ==
                     Path(target["path"]).read_bytes(), "native/Python evidence binding changed")
        expected_labels = {"payload-crc", "truncated", "same-version"}
        if not bootstrap:
            expected_labels |= {"wrong-base", "wrong-base-sha"}
            prep.require(group["legacy_native"] == prep.read(OUT / "logs" / (name + "-legacy.stdout")),
                         "legacy decoder evidence changed")
        prep.require({item["name"] for item in group["negatives"]} == expected_labels,
                     "negative package cases missing")
        for item in group["negatives"]:
            prep.require(item["native"] == prep.read(OUT / "logs" / (name + "-" + item["name"] + ".stdout")) and
                         item["native"]["passed"] is True and item["native"]["prepares"] == 0,
                         "negative package proof changed")
    prep.require(value["groups"]["pressure"]["package"]["bytes"] == 1048576,
                 "pressure package no longer has the reference length")


def load_for_context(c, specification):
    """Strict view for the existing serial session backend, not a new runner."""
    value = load()
    name = specification["asset_group"]
    prep.require(name in value["groups"], "unknown prepared package group")
    group = value["groups"][name]
    target = value["images"]["aa" if name == "bootstrap" else "ab"]
    receiver_bindings = value["historical_receiver_bindings"] if name == "bootstrap" else value["images"]["aa"]["bindings"]
    prep.require(c.receiver_version == group["receiver"] and c.bindings == receiver_bindings and
                 c.previous_assets["target"] == group["base"], "prepared PATCH receiver/predecessor differs")
    prep.require(specification["receiver"] == group["receiver"] and
                 specification["target_version"] == group["target_version"] and
                 specification["version_name"] == target["identity"]["version_name"] and
                 specification["kind"] == group["kind"] and
                 specification["served_name"] == group["served_name"] and specification["assets"] == RELATIVE,
                 "session specification does not match the frozen package")
    return dict(result=RESULT, specification=specification, receiver=group["base"], receiver_bindings=receiver_bindings,
        target=group["target"], target_identity=target["identity"], target_bindings=target["bindings"],
        package=group["package"], package_kind=group["kind"], header=group["header"], decoded=group["native"],
        decoded_image=group["decoded"], negatives=group["negatives"], manifest=prep.record(OUT / "result.json"))


def prepare():
    if (OUT / "result.json").exists():
        return dict(result=load()["result"], reused=True)
    prep.checked(OUT)
    prep.require(not OUT.exists(), "preserve partial package preparation and nonce")
    source = prep.verify_source()
    build = prep.read(FIRMWARE / "build.json")
    prep.require(build["result"] == EXPECTED_BUILD_RESULT and build["errors"] == 0 and build[EXPECTED_BUILD_FEATURE] and
                 not build["boot_built"] and not build["finalized"], "complete candidate App build required")
    prep.verify_records([build["source"], *build["artifacts"]])
    artifacts = {Path(item["path"]).suffix: {key: item[key] for key in ("path", "bytes", "sha256")}
                 for item in build["artifacts"]}
    y = prep.read(prep.Y_ASSETS)
    host = prep.read(prep.HOST_TESTS)
    patch_decoders = {mode: next(item for item in host["binaries"]
                     if Path(item["path"]).name == f"reference-{mode}.exe") for mode in (0, 1)}
    full_decoder = prep.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    inputs = [prep.record(path) for path in (FIRMWARE / "build.json", prep.Y_ASSETS, prep.HOST_TESTS,
        PROOF, BSDIFF, ROOT / "bsdiff_lzma_AES128-main/bsdiff/main.c", ROOT / "Tools/ota/baud_mcu.py",
        ROOT / ".cache/p34-next/n03_bindings.py", prep.FW / "Tools/etu_pack.py", prep.FW / "Tools/etu_unpack.py")]
    inputs += [y["target"], y["target_bindings"]["whole_boot"], *artifacts.values(), *patch_decoders.values(), full_decoder]
    inputs += [prep.record(path) for path in EXTRA_INPUTS]
    equivalence = decoder_equivalence(host)
    inputs += [item["candidate"] for item in equivalence]
    prep.verify_records(inputs)
    for relative in ("intent.json", "result.json", "failed.json", "images", "packages", "negative", "logs",
                     "compact-work/temp_diff.data", "compact-work/compact.native", "pressure", "sources"):
        prep.checked(OUT / relative)
    env, paths = environment()
    os.environ.update({name: str(path) for name, path in paths.items()})
    for folder in ("images", "packages", "negative", "compact-work", "sources"):
        prep.checked(OUT / folder).mkdir(parents=True, exist_ok=True)
    inputs.append(prep.raw(OUT / "sources/p34_patch_assets.py", Path(__file__).read_bytes()))
    inputs.append(prep.raw(OUT / "sources/p34_patch_preparation.py", Path(prep.__file__).read_bytes()))
    prep.save(OUT / "intent.json", dict(inputs=inputs, environment=paths,
        versions=dict(receiver=prep.AA, target=prep.AB), search_budget=SEARCH_BUDGET, hardware=False,
        vendor_temporary_file=str(OUT / "compact-work/temp_diff.data")))
    try:
        pack, unpack = packers()
        raw_image = Path(artifacts[".bin"]["path"]).read_bytes()
        images = {}
        for label, version, version_name in (("aa", prep.AA, prep.AA_NAME), ("ab", prep.AB, prep.AB_NAME)):
            image = bytearray(raw_image)
            image[0x400:0x460] = pack.build_fw_header(bytes(image), version_name, 1786320000)
            data = bytes(image)
            details = identity(data, unpack)
            prep.require(details["version_code"] == version and data[:0x400] + data[0x460:] ==
                         raw_image[:0x400] + raw_image[0x460:], "finalization changed executable bytes")
            image_record = prep.raw(OUT / "images" / (str(version) + ".bin"), data)
            images[label] = dict(image=image_record, identity=details,
                bindings=bindings(y, image_record, details, artifacts, build["layout"]["constants"]))
        aa = Path(images["aa"]["image"]["path"]).read_bytes()
        ab = Path(images["ab"]["image"]["path"]).read_bytes()
        old_y = Path(y["target"]["path"]).read_bytes()
        bootstrap = prep.raw(OUT / "packages/p34-coalesce-bootstrap-full.etu",
                             wrap_payload(pack, pack.lzma_alone_encode(aa), old_y, aa, kind="full"))
        vendor = OUT / "compact-work/compact.native"
        run("vendor-compact", [BSDIFF, images["aa"]["image"]["path"], images["ab"]["image"]["path"],
                               vendor, "-aes", "0", "-dict", "16"], env, cwd=OUT / "compact-work")
        native = vendor.read_bytes()
        prep.require(len(native) > 40 and not (OUT / "compact-work/temp_diff.data").exists(),
                     "vendor output missing or its bounded temporary file remains")
        inner = pack.normalize_patch_header(native[:40], len(native) - 40, aa, ab)
        compact = prep.raw(OUT / "packages/p34-coalesce-compact-patch.etu",
                           wrap_payload(pack, inner + native[40:], aa, ab, kind="patch"))
        proof = size_proof(pack, unpack)
        selection = proof["search"](aa, ab, seed=1931, budget=SEARCH_BUDGET)
        prep.save(OUT / "pressure/proof/selection.json", selection)
        proof["witness"](aa, ab, selection)
        pressure = prep.record(OUT / "pressure/cases/reference-1MiB.etu")
        groups = {}
        for name, package, base, target, receiver, version, kind in (
            ("bootstrap", bootstrap, y["target"], images["aa"]["image"], y["target_identity"]["version_code"], prep.AA, "full"),
            ("compact", compact, images["aa"]["image"], images["ab"]["image"], prep.AA, prep.AB, "patch"),
            ("pressure", pressure, images["aa"]["image"], images["ab"]["image"], prep.AA, prep.AB, "patch")):
            blob, base_bytes, target_bytes = (Path(item["path"]).read_bytes() for item in (package, base, target))
            header = package_header(blob, kind, receiver, version, base["sha256"], unpack)
            decoded = prep.raw(OUT / "images" / (name + "-decoded.bin"),
                               decode_python(blob, base_bytes, target_bytes, kind, unpack))
            decoder = full_decoder if kind == "full" else patch_decoders[1]
            positive = native_verify(name + "-native", package, base, target, "ok", decoder, env)
            default = native_verify(name + "-legacy", package, base, target, "ok", patch_decoders[0], env) if kind == "patch" else None
            if kind == "patch":
                prep.require(positive["program_calls"] == (len(target_bytes) + 1023) // 1024,
                             "coalescing program count differs from full-buffer/tail bound")
            changes = [("payload-crc", blob[:104] + bytes([blob[104] ^ 1]) + blob[105:], "payload_crc"),
                       ("truncated", blob[:-1], "package_length"),
                       ("same-version", header_mutation(blob, 40, struct.pack("<I", receiver)), "version")]
            if kind == "patch":
                changes += [("wrong-base", header_mutation(blob, 44, struct.pack("<I", receiver - 1)), "base_vcode"),
                            ("wrong-base-sha", header_mutation(blob, 52, bytes([blob[52] ^ 1])), "base_sha8")]
            negatives = []
            for label, changed, expected in changes:
                changed_record = prep.raw(OUT / "negative" / (name + "-" + label + ".etu"), changed)
                rejected = native_verify(name + "-" + label, changed_record, base, target, expected, decoder, env)
                prep.require(rejected["prepares"] == 0, "invalid package reached candidate preparation")
                negatives.append(dict(name=label, package=changed_record, native=rejected))
            groups[name] = dict(package=package, base=base, target=target, receiver=receiver, target_version=version,
                kind=kind, header=header, decoded=decoded, native=positive, legacy_native=default, negatives=negatives,
                served_name="p34-coalesce-" + name + ("-full.etu" if kind == "full" else "-patch.etu"))
        prep.require(groups["pressure"]["package"]["bytes"] == 1048576, "reference is not exactly 1 MiB")
        prep.verify_records(inputs)
        outputs = [prep.record(path) for path in sorted(OUT.rglob("*")) if path.is_file()]
        value = dict(result=RESULT, inputs=inputs, outputs=outputs, images=images, groups=groups,
            decoder_equivalence=equivalence,
            historical_receiver=y["target"], historical_receiver_bindings=y["target_bindings"],
            pressure_selection=selection, pressure_representation="legal deliberately non-minimal progressing controls",
            formal_reference_admitted=False, alternative_targets="compact and pressure both AA-to-AB; do not run sequentially",
            hardware=False, independent_acceptance=False, runtime_stack_high_water=False)
        validate_manifest(value)
        prep.save(OUT / "result.json", value)
        return dict(result=RESULT, packages={name: item["package"]["bytes"] for name, item in groups.items()},
                    candidate_bytes=len(aa), reused=False)
    except Exception as error:
        prep.save(OUT / "failed.json", dict(error=str(error), preserve_partial_assets=True, hardware=False))
        raise
