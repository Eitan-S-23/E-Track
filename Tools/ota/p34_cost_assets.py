"""Two legal successors for install-cost diagnostics on the retained new Boot."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host
import p34_patch_assets as shared
import p34_boot_ota_assets as boot
import p34_historical_inputs as historical

RELATIVE = ".cache/p34-cost/assets/result-v2.json"
BUILD_REPORT = ".cache/p34-cost/build/result.json"


def diagnostic_package():
    return boot.diagnostic_package()


def load():
    s = cli.Store(ROOT)
    value = s.read(ROOT / RELATIVE)
    cli.require(value["result"] == "COST_ASSETS_VERIFIED" and not value["hardware"], "cost assets unverified")
    for item in value["inputs"] + value["outputs"]:
        historical.resolve(item)
    for name, spec in cli.COST_GROUPS.items():
        g = value["groups"][spec["asset_group"]]
        cli.require(g["specification"] == spec and g["target_identity"]["version_code"] == spec["target_version"] and
                    g["target_bindings"]["whole_boot"]["sha256"] == boot.BOOT_SHA and
                    g["receiver_bindings"]["whole_boot"] == g["target_bindings"]["whole_boot"] and
                    g["receiver_bindings"]["boot_map"] == g["target_bindings"]["boot_map"], "cost version/Boot mismatch")
        cli.require(all(g["decoded"][k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
                    len(g["negatives"]) == 4 and all(x["native"]["passed"] and x["native"]["prepares"] == 0 for x in g["negatives"]),
                    "cost decoder proof missing")
    a, b = (value["groups"][name] for name in ("bootstrap", "measure"))
    cli.require(b["receiver_bindings"] == a["target_bindings"] and b["receiver"] == a["target"], "cost pair disconnected")
    x, y = (Path(g["target"]["path"]).read_bytes() for g in (a, b))
    cli.require(x[:0x400] + x[0x460:] == y[:0x400] + y[0x460:], "measurement changes executable")
    return value


def load_for_context(c, specification):
    cli.require(specification in cli.COST_GROUPS.values(), "unknown cost specification")
    g = load()["groups"][specification["asset_group"]]
    cli.require(c.receiver_version == specification["receiver"] and c.bindings == g["receiver_bindings"] and
                c.previous_assets["target"] == g["receiver"], "wrong cost receiver")
    return dict(g, manifest=cli.record(ROOT / RELATIVE))


def prepare():
    s = cli.Store(ROOT)
    out = s.checked(ROOT / Path(RELATIVE).parent)
    cli.require(not out.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no external key override")
    run = s.run("20260930T133457-87100")
    cli.require(s.current() == run.name, "actual30238 predecessor changed")
    pointer = s.read(run / "analysis/latest.json")
    report = s.read(pointer["report"]["path"])
    cli.require(cli.record(pointer["report"]["path"]) == pointer["report"] and report["result"] == "FULL_INSTALL_VERIFIED",
                "predecessor completion changed")
    plan = s.read(run / "plan.json")
    bindings = plan["target_bindings"]
    cli.require(plan["group"] == cli.BOOT_COPY_GROUP and bindings["profile"]["identity"]["version_code"] == 30238 and
                bindings["whole_boot"]["sha256"] == boot.BOOT_SHA, "wrong retained30238")
    for name in ("s04", "network"):
        state = cli.owner_state(s, run / "runtime" / name)
        cli.require(state["state"] == "CLOSED" and state["receipt"]["worker_exit"] == 0 and
                    not state["receipt"]["forced_termination"], "predecessor owner not closed")
    closure_path = run / "cells/s04/installed-mcu/closure.json"
    closure = s.read(closure_path)
    cli.require(closure["retained_verified"] and closure["reader_closed"], "predecessor native closure failed")
    for image, expected in (("app", bindings["profile"]["image"]["sha256"]), ("boot", boot.BOOT_SHA)):
        item = closure["final_identity"][image]
        cli.require(cli.record(item["path"]) == item and item["sha256"] == expected, "predecessor raw identity changed")
    build = s.read(ROOT / BUILD_REPORT)
    review = s.read(host.AREA / "build-check/result.json")
    cli.require(build["result"] == "COST_APP_BUILT" and build["errors"] == 0 and not build["boot_built"] and
                review["default_off_object_identical"] and not review["new_warnings"], "candidate build unverified")
    artifacts = {Path(i["path"]).suffix: i for i in build["artifacts"]}
    env = host.environment(s, out)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("cost_pack", host.AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("cost_unpack", host.AREA / "f/Tools/etu_unpack.py")
    tools = cli.load_module("cost_package_tools", ROOT / "Tools/ota/prepare_baud_assets.py")
    constants = s.read(ROOT / ".cache/p34ab/assets/session-assets.json")["constants"]
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    inputs = [pointer["report"], cli.record(run / "plan.json"), cli.record(closure_path), *closure["final_identity"].values(),
        cli.record(ROOT / BUILD_REPORT), cli.record(host.AREA / "build-check/result.json"),
        cli.record(host.AREA / "tests/result.json"), build["source"], decoder, *artifacts.values(),
        bindings["profile"]["image"], bindings["profile"]["map"], bindings["whole_boot"], bindings["boot_map"],
        cli.record(Path(__file__)), cli.record(Path(host.__file__)), cli.record(Path(shared.__file__)),
        cli.record(Path(pack.__file__)), cli.record(Path(unpack.__file__))]
    for item in inputs + s.read(build["source"]["path"])["files"]:
        cli.require(cli.record(item["path"]) == item, "prepared source changed")
    groups, outputs = {}, []
    for name, spec in cli.COST_GROUPS.items():
        tag = spec["asset_group"]
        receiver = bindings["profile"]["image"]
        raw = bytearray(Path(artifacts[".bin"]["path"]).read_bytes())
        raw[0x400:0x460] = pack.build_fw_header(bytes(raw), spec["version_name"], 1786320000)
        target = s.raw(out / (tag + ".bin"), bytes(raw))
        identity = shared.identity(bytes(raw), unpack)
        blob = shared.wrap_payload(pack, pack.lzma_alone_encode(bytes(raw)), Path(receiver["path"]).read_bytes(), bytes(raw), kind="full")
        package = s.raw(out / (tag + ".etu"), blob)
        def native(label, record, expected):
            data = host.command(s, out, label, [decoder["path"], record["path"], receiver["path"], target["path"], expected], env, 180)
            return json.loads(data)
        decoded = native(tag + "-positive", package, "ok")
        negatives = []
        for label, broken, expected in tools.negatives(blob, spec["receiver"]):
            item = s.raw(out / (tag + "-" + label + ".etu"), broken)
            negatives.append(dict(name=label, native=native(tag + "-" + label, item, expected), package=item))
            outputs.append(item)
        target_bindings = shared.bindings(dict(target_bindings=bindings), target, identity, artifacts, constants)
        groups[tag] = dict(result="COST_ASSETS_VERIFIED", specification=spec, receiver=receiver,
            receiver_bindings=bindings, target=target, target_identity=identity, target_bindings=target_bindings,
            package=package, package_kind="full", header=tools.package_info(blob, spec["receiver"], spec["target_version"]),
            decoded=decoded, decoded_image=target, negatives=negatives)
        outputs.extend((target, package))
        bindings = copy.deepcopy(target_bindings)
    outputs += [cli.record(p) for p in out.glob("*.log")]
    s.write(ROOT / RELATIVE, dict(result="COST_ASSETS_VERIFIED", hardware=False, groups=groups, inputs=inputs, outputs=outputs))
    load()
    print("COST_ASSETS_VERIFIED", {k:v["package"]["bytes"] for k,v in groups.items()})


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    prepare()
