"""Write-once header-only successor for the reconnect cadence screen."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_erase_assets as erase
import p34_install_cost as host
import p34_patch_assets as shared
import p34_historical_inputs as historical

RELATIVE = ".cache/p34-reconnect/assets/result.json"
PREDECESSOR = "20261001T112936-16300"
REPORT_SHA = "e68b4fde5e7d477c1a09097f88836ee0a17a2039d7fe80756fbceb77625c9225"
SPEC = dict(receiver=30242, target_version=30243, version_name="3.2.43-p34r",
    served_name="p34-reconnect-full.etu", release_key="p34-reconnect", kind="full",
    assets=RELATIVE, asset_group="measure", predecessor_group="erase-measure")


def diagnostic_package():
    return erase.diagnostic_package()


def load():
    s = cli.Store(ROOT)
    value = s.read(ROOT / RELATIVE)
    cli.require(value["result"] == "RECONNECT_ASSETS_VERIFIED" and not value["hardware"],
                "reconnect assets unverified")
    for item in value["inputs"] + value["outputs"]:
        historical.resolve(item)
    g = value["groups"]["measure"]
    cli.require(g["specification"] == SPEC and g["target_identity"]["version_code"] == 30243 and
                g["receiver_bindings"]["profile"]["identity"]["version_code"] == 30242 and
                g["receiver_bindings"]["whole_boot"] == g["target_bindings"]["whole_boot"] and
                g["target_bindings"]["whole_boot"]["sha256"] == erase.boot.BOOT_SHA and
                g["receiver_bindings"]["boot_map"] == g["target_bindings"]["boot_map"], "identity/Boot mismatch")
    x, y = (Path(g[k]["path"]).read_bytes() for k in ("receiver", "target"))
    cli.require(len(x) == len(y) and x[:0x400] + x[0x460:] == y[:0x400] + y[0x460:],
                "reconnect screen changed executable bytes")
    expected = copy.deepcopy(g["receiver_bindings"])
    expected["profile"].update(image=g["target"], identity=g["target_identity"], prefix=y[:0x460].hex())
    cli.require(g["target_bindings"] == expected, "header-only runtime binding drift")
    cli.require(all(g["decoded"][k] for k in
        ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
        len(g["negatives"]) == 4 and all(n["native"]["passed"] and n["native"]["prepares"] == 0
        for n in g["negatives"]), "decoder proof missing")
    return value


def load_for_context(c, specification):
    cli.require(specification == SPEC, "unknown reconnect specification")
    g = load()["groups"]["measure"]
    cli.require(c.receiver_version == 30242 and c.bindings == g["receiver_bindings"] and
                c.previous_assets["target"] == g["receiver"], "wrong reconnect receiver")
    return dict(g, manifest=cli.record(ROOT / RELATIVE))


def prepare():
    s = cli.Store(ROOT)
    out = s.checked(ROOT / Path(RELATIVE).parent)
    cli.require(not out.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no key override")
    previous = erase.load()["groups"]["measure"]
    run = s.run(PREDECESSOR)
    cli.require(s.current() == PREDECESSOR, "actual predecessor changed")
    pointer = s.read(run / "analysis/latest.json")
    report = s.read(pointer["report"]["path"])
    cli.require(cli.record(pointer["report"]["path"]) == pointer["report"] and
                pointer["report"]["sha256"] == REPORT_SHA and report["result"] == "FULL_INSTALL_VERIFIED",
                "completed30242 report changed")
    plan = s.read(run / "plan.json")
    bindings = plan["target_bindings"]
    cli.require(plan["group"] == "erase-measure" and bindings == previous["target_bindings"],
                "retained30242 binding changed")
    for name in ("s04", "network"):
        state = cli.owner_state(s, run / "runtime" / name)
        cli.require(state["state"] == "CLOSED" and state["receipt"]["worker_exit"] == 0 and
                    not state["receipt"]["forced_termination"], "predecessor owner not closed")
    closure_path = run / "cells/s04/installed-mcu/closure.json"
    closure = s.read(closure_path)
    cli.require(closure["retained_verified"] and closure["reader_closed"], "native closure failed")
    for name, sha in (("app", previous["target"]["sha256"]), ("boot", erase.boot.BOOT_SHA)):
        item = closure["final_identity"][name]
        cli.require(cli.record(item["path"]) == item and item["sha256"] == sha, "raw identity changed")
    env = host.environment(s, out)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("reconnect_pack", erase.candidate.AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("reconnect_unpack", erase.candidate.AREA / "f/Tools/etu_unpack.py")
    tools = cli.load_module("reconnect_package_tools", ROOT / "Tools/ota/prepare_baud_assets.py")
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    receiver = previous["target"]
    inputs = [cli.record(ROOT / erase.RELATIVE), pointer["report"], cli.record(run / "plan.json"),
        cli.record(closure_path), *closure["final_identity"].values(), receiver, decoder,
        cli.record(Path(__file__)), cli.record(Path(pack.__file__)), cli.record(Path(unpack.__file__)),
        cli.record(Path(tools.__file__)), cli.record(Path(shared.__file__)), cli.record(Path(host.__file__))]
    for item in inputs:
        historical.resolve(item)
    raw = bytearray(Path(receiver["path"]).read_bytes())
    raw[0x400:0x460] = pack.build_fw_header(bytes(raw), SPEC["version_name"], 1786320000)
    target = s.raw(out / "measure.bin", bytes(raw))
    identity = shared.identity(bytes(raw), unpack)
    blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)),
        Path(receiver["path"]).read_bytes(), bytes(raw), kind="full")
    package = s.raw(out / "measure.etu", blob)
    def native(label, item, expected):
        return json.loads(host.command(s, out, label,
            [decoder["path"], item["path"], receiver["path"], target["path"], expected], env, 180))
    decoded = native("positive", package, "ok")
    negatives, outputs = [], [target, package]
    for label, broken, expected in tools.negatives(blob, SPEC["receiver"]):
        item = s.raw(out / (label + ".etu"), broken)
        negatives.append(dict(name=label, native=native(label, item, expected), package=item))
        outputs.append(item)
    target_bindings = copy.deepcopy(bindings)
    target_bindings["profile"]["image"] = target
    target_bindings["profile"]["identity"] = identity
    target_bindings["profile"]["prefix"] = bytes(raw[:0x460]).hex()
    g = dict(result="RECONNECT_ASSETS_VERIFIED", specification=SPEC, receiver=receiver,
        receiver_bindings=bindings, target=target, target_identity=identity, target_bindings=target_bindings,
        package=package, package_kind="full", header=tools.package_info(blob, 30242, 30243),
        decoded=decoded, decoded_image=target, negatives=negatives)
    outputs += [cli.record(p) for p in out.glob("*.log")]
    s.write(ROOT / RELATIVE, dict(result="RECONNECT_ASSETS_VERIFIED", hardware=False,
        groups=dict(measure=g), inputs=inputs, outputs=outputs))
    load()
    print("RECONNECT_ASSETS_VERIFIED", package["bytes"], package["sha256"], flush=True)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    prepare()
