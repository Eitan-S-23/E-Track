"""One host-only continuation of the exhausted PATCH32 compression search.

Existing images, ciphertext/nonces and the original failure remain immutable.
This is not a general retry path for partially executed package validation.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_patch32_assets as adapter

cli, ROOT = adapter.cli, adapter.ROOT
TOTAL_BUDGET = 512


def admit(store, api):
    adapter.verify_admission(store)
    cli.require(store.current() == store.read(adapter.ADMISSION)["predecessor"]["run"],
                "PATCH32 recovery requires the unchanged completed30226 owner")
    out = api.OUT
    failure = store.read(out / "failed.json")
    cli.require(failure == dict(error="Bounded compression budget exhausted; no exact witness",
                               preserve_partial_assets=True, hardware=False), "not a search-budget failure")
    intent = store.read(out / "intent.json")
    cli.require(intent["versions"] == dict(receiver=30227, target=30228) and
                intent["search_budget"] == 128 and intent["hardware"] is False, "unexpected original intent")
    api.prep.verify_records(intent["inputs"])
    for name in ("result.json", "search-continuation", "pressure/proof", "pressure/cases"):
        cli.require(not store.checked(out / name).exists(), "preserve partial recovery: " + name)
    cli.require(not list((out / "negative").iterdir()) and
                not list((out / "images").glob("*-decoded.bin")), "validation already attempted")
    rows = [store.read(path) for path in (out / "pressure/logs").glob("measure-*.json")]
    cli.require(len(rows) == 128 and all(row["etu_bytes"] != 1048576 for row in rows),
                "original bounded search evidence differs")
    return intent, rows


def images_and_packages(api, intent, rows):
    prep = api.prep
    build, receiver = prep.read(api.FIRMWARE / "build.json"), prep.read(prep.Y_ASSETS)
    artifacts = {Path(item["path"]).suffix: {key: item[key] for key in ("path", "bytes", "sha256")}
                 for item in build["artifacts"]}
    pack, unpack = api.packers()
    original = Path(artifacts[".bin"]["path"]).read_bytes()
    images = {}
    for label, version, name in (("aa", 30227, prep.AA_NAME), ("ab", 30228, prep.AB_NAME)):
        record = prep.record(api.OUT / "images" / (str(version) + ".bin"))
        data = Path(record["path"]).read_bytes()
        expected = bytearray(original)
        expected[0x400:0x460] = pack.build_fw_header(original, name, 1786320000)
        cli.require(data == bytes(expected), "partial finalized image differs from original build")
        details = api.identity(data, unpack)
        images[label] = dict(image=record, identity=details,
            bindings=api.bindings(receiver, record, details, artifacts, build["layout"]["constants"]))
    aa, ab = (Path(images[label]["image"]["path"]).read_bytes() for label in ("aa", "ab"))
    cli.require(all(row["base_sha256"] == images["aa"]["image"]["sha256"] and
                    row["target_sha256"] == images["ab"]["image"]["sha256"] and row["seed"] == 1931
                    for row in rows), "search input identity differs")
    packages = {name: prep.record(api.OUT / "packages" / ("p34-coalesce-" + name + suffix))
                for name, suffix in (("bootstrap", "-full.etu"), ("compact", "-patch.etu"))}
    for name, base, target, kind, version in (
            ("bootstrap", Path(receiver["target"]["path"]).read_bytes(), aa, "full", 30226),
            ("compact", aa, ab, "patch", 30227)):
        blob = Path(packages[name]["path"]).read_bytes()
        api.package_header(blob, kind, version, version + 1, api.hashlib.sha256(base).hexdigest(), unpack)
        api.decode_python(blob, base, target, kind, unpack)
    return pack, unpack, receiver, images, packages


def validate_groups(api, unpack, receiver, images, packages, env):
    """Use the same positive and pre-prepare negative oracles as first preparation."""
    prep = api.prep
    host = prep.read(prep.HOST_TESTS)
    decoders = {mode: next(item for item in host["binaries"]
                          if Path(item["path"]).name == f"reference-{mode}.exe") for mode in (0, 1)}
    full = prep.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    groups = {}
    for name, package in packages.items():
        bootstrap = name == "bootstrap"
        base = receiver["target"] if bootstrap else images["aa"]["image"]
        target = images["aa" if bootstrap else "ab"]["image"]
        kind, version = ("full", 30226) if bootstrap else ("patch", 30227)
        blob, base_bytes, target_bytes = (Path(item["path"]).read_bytes() for item in (package, base, target))
        header = api.package_header(blob, kind, version, version + 1, base["sha256"], unpack)
        decoded = prep.raw(api.OUT / "images" / (name + "-decoded.bin"),
                           api.decode_python(blob, base_bytes, target_bytes, kind, unpack))
        decoder = full if bootstrap else decoders[1]
        positive = api.native_verify(name + "-native", package, base, target, "ok", decoder, env)
        legacy = None if bootstrap else api.native_verify(name + "-legacy", package, base, target, "ok", decoders[0], env)
        if not bootstrap:
            cli.require(positive["program_calls"] == (len(target_bytes) + 1023) // 1024, "coalescing count differs")
        changes = [("payload-crc", blob[:104] + bytes([blob[104] ^ 1]) + blob[105:], "payload_crc"),
                   ("truncated", blob[:-1], "package_length"),
                   ("same-version", api.header_mutation(blob, 40, struct.pack("<I", version)), "version")]
        if not bootstrap:
            changes += [("wrong-base", api.header_mutation(blob, 44, struct.pack("<I", version - 1)), "base_vcode"),
                        ("wrong-base-sha", api.header_mutation(blob, 52, bytes([blob[52] ^ 1])), "base_sha8")]
        negatives = []
        for label, data, expected in changes:
            negative = prep.raw(api.OUT / "negative" / (name + "-" + label + ".etu"), data)
            result = api.native_verify(name + "-" + label, negative, base, target, expected, decoder, env)
            cli.require(result["prepares"] == 0, "negative package reached prepare")
            negatives.append(dict(name=label, package=negative, native=result))
        groups[name] = dict(package=package, base=base, target=target, receiver=version, target_version=version + 1,
            kind=kind, header=header, decoded=decoded, native=positive, legacy_native=legacy, negatives=negatives,
            served_name="p34-coalesce-" + name + ("-full.etu" if bootstrap else "-patch.etu"))
    return groups


def resume(store):
    api = adapter.engine()
    with store.command_lock():
        intent, rows = admit(store, api)
        pack, unpack, receiver, images, packages = images_and_packages(api, intent, rows)
        recovery = store.checked(api.OUT / "search-continuation")
        # Check every existing descendant as well as all new output parents.
        for path in api.OUT.rglob("*"):
            store.checked(path)
        for name in ("intent.json", "result.json", "failed.json", "source.py"):
            store.checked(recovery / name)
        for name in ("pressure/proof", "pressure/cases", "images", "negative", "logs", "result.json"):
            store.checked(api.OUT / name)
        preserved = [cli.record(path) for path in sorted(api.OUT.rglob("*")) if path.is_file()]
        source = store.raw(recovery / "source.py", Path(__file__).read_bytes())
        store.write(recovery / "intent.json", dict(originals=preserved, source=source,
            cached_measurements=128, max_new_measurements=TOTAL_BUDGET - 128, total_budget=TOTAL_BUDGET,
            operation="continue deterministic compression search; never rewrap existing packages", device_operations=0))
        try:
            env, paths = api.environment()
            os.environ.update(paths)
            proof = api.size_proof(pack, unpack)
            aa, ab = (Path(images[label]["image"]["path"]).read_bytes() for label in ("aa", "ab"))
            selection = proof["search"](aa, ab, seed=1931, budget=TOTAL_BUDGET)
            api.prep.save(api.OUT / "pressure/proof/selection.json", selection)
            proof["witness"](aa, ab, selection)
            packages["pressure"] = cli.record(api.OUT / "pressure/cases/reference-1MiB.etu")
            groups = validate_groups(api, unpack, receiver, images, packages, env)
            api.prep.verify_records(preserved + intent["inputs"])
            store.write(recovery / "result.json", dict(result="PATCH32_SEARCH_CONTINUED", originals_unchanged=True,
                selection=selection, device_operations=0, original_failure=cli.record(api.OUT / "failed.json")))
            inputs = intent["inputs"] + [source, cli.record(recovery / "intent.json")]
            outputs = [cli.record(path) for path in sorted(api.OUT.rglob("*")) if path.is_file()]
            value = dict(result=api.RESULT, inputs=inputs, outputs=outputs, images=images, groups=groups,
                decoder_equivalence=api.decoder_equivalence(api.prep.read(api.prep.HOST_TESTS)),
                historical_receiver=receiver["target"], historical_receiver_bindings=receiver["target_bindings"],
                pressure_selection=selection, pressure_representation="legal deliberately non-minimal progressing controls",
                formal_reference_admitted=False, alternative_targets="compact and pressure both AA-to-AB; do not run sequentially",
                hardware=False, independent_acceptance=False, runtime_stack_high_water=False)
            api.validate_manifest(value)
            store.write(api.OUT / "result.json", value)
            adapter.load()
            return dict(result=api.RESULT, manifest=cli.record(api.OUT / "result.json"), device_operations=0,
                        packages={name: item["package"]["bytes"] for name, item in groups.items()})
        except Exception as error:
            store.write(recovery / "failed.json", dict(error=str(error), preserve_partial_assets=True, device_operations=0))
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    cli.require(args.root == ROOT and Path.cwd() == ROOT and sys.flags.isolated and
                sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit project root required")
    print(json.dumps(resume(cli.Store(ROOT))), flush=True)
