"""Immutable two-cell payload-erase screen, retaining the verified Boot."""
import copy
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host
import p34_erase_candidate as candidate
import p34_patch_assets as shared
import p34_boot_ota_assets as boot
import p34_historical_inputs as historical

RELATIVE = ".cache/p34-erase/assets/result.json"
BUILD_REPORT = ".cache/p34-erase/build/result.json"
PREDECESSOR = "20260930T175922-37800"
REPORT_SHA = "547c0048dac76c0980050e46092b4c5cfbbfc2f503e71d5e025a5a380ff2e47e"


def diagnostic_package():
    return boot.diagnostic_package()


def load():
    s = cli.Store(ROOT)
    value = s.read(ROOT / RELATIVE)
    cli.require(value["result"] == "ERASE_ASSETS_VERIFIED" and not value["hardware"], "erase assets unverified")
    for item in value["inputs"] + value["outputs"]:
        historical.resolve(item)
    for spec in cli.ERASE_GROUPS.values():
        g = value["groups"][spec["asset_group"]]
        cli.require(g["specification"] == spec and g["target_identity"]["version_code"] == spec["target_version"] and
                    g["target_bindings"]["whole_boot"]["sha256"] == boot.BOOT_SHA and
                    g["receiver_bindings"]["whole_boot"] == g["target_bindings"]["whole_boot"] and
                    g["receiver_bindings"]["boot_map"] == g["target_bindings"]["boot_map"], "erase version/Boot mismatch")
        cli.require(all(g["decoded"][k] for k in ("passed", "byte_identical", "boot_ok", "guards_ok", "workspace_lifecycle_ok")) and
                    len(g["negatives"]) == 4 and all(x["native"]["passed"] and x["native"]["prepares"] == 0 for x in g["negatives"]),
                    "erase decoder proof missing")
    a, b = (value["groups"][name] for name in ("bootstrap", "measure"))
    cli.require(b["receiver_bindings"] == a["target_bindings"] and b["receiver"] == a["target"], "erase pair disconnected")
    x, y = (Path(g["target"]["path"]).read_bytes() for g in (a, b))
    cli.require(x[:0x400] + x[0x460:] == y[:0x400] + y[0x460:], "measurement changes executable")
    return value


def load_for_context(c, specification):
    cli.require(specification in cli.ERASE_GROUPS.values(), "unknown erase specification")
    g = load()["groups"][specification["asset_group"]]
    cli.require(c.receiver_version == specification["receiver"] and c.bindings == g["receiver_bindings"] and
                c.previous_assets["target"] == g["receiver"], "wrong erase receiver")
    return dict(g, manifest=cli.record(ROOT / RELATIVE))


def prepare():
    s = cli.Store(ROOT)
    out = s.checked(ROOT / Path(RELATIVE).parent)
    cli.require(not out.exists() and not os.environ.get("OTA_AES_KEY"), "preserve assets/no external key override")
    run = s.run(PREDECESSOR)
    cli.require(s.current() == run.name, "actual30240 predecessor changed")
    pointer = s.read(run / "analysis/latest.json")
    report = s.read(pointer["report"]["path"])
    cli.require(cli.record(pointer["report"]["path"]) == pointer["report"] and
                pointer["report"]["sha256"] == REPORT_SHA and report["result"] == "FULL_INSTALL_VERIFIED",
                "predecessor completion changed")
    plan = s.read(run / "plan.json")
    bindings = plan["target_bindings"]
    cli.require(plan["group"] == "cost-measure" and bindings["profile"]["identity"]["version_code"] == 30240 and
                bindings["whole_boot"]["sha256"] == boot.BOOT_SHA, "wrong retained30240")
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
    review_path = candidate.AREA / "build-review/result.json"
    review = s.read(review_path)
    tests = s.read(review["tests"]["path"])
    cli.require(build["result"] == "ERASE_APP_BUILT" and build["errors"] == 0 and not build["boot_built"] and
                review["result"] == "ERASE_BUILD_REVIEW_PASS" and review["production_unchanged"] and
                review["build"] == cli.record(ROOT / BUILD_REPORT) and review["new_warnings"] == 0 and
                tests["result"] == "ERASE_HOST_PASS" and tests["errors"] == 0, "candidate build/tests unverified")
    for name in candidate.OVERLAY:
        cli.require((ROOT / name).read_bytes() == (candidate.AREA / "f" / name).read_bytes(), "production overlay changed")
    artifacts = {Path(i["path"]).suffix: i for i in build["artifacts"]}
    env = host.environment(s, out)
    os.environ.update(env)
    sys.path.insert(0, str(Path(sys.base_prefix) / "Lib/site-packages"))
    pack = cli.load_module("erase_pack", candidate.AREA / "f/Tools/etu_pack.py")
    unpack = cli.load_module("erase_unpack", candidate.AREA / "f/Tools/etu_unpack.py")
    tools = cli.load_module("erase_package_tools", ROOT / "Tools/ota/prepare_baud_assets.py")
    constants = s.read(ROOT / ".cache/p34ab/assets/session-assets.json")["constants"]
    decoder = s.read(ROOT / ".cache/p34-next/n03/assets/result.json")["decoder"]
    inputs = [pointer["report"], cli.record(run / "plan.json"), cli.record(closure_path), *closure["final_identity"].values(),
        cli.record(ROOT / BUILD_REPORT), cli.record(review_path), review["tests"], review["source"], *review["logs"],
        *tests["inputs"], tests["hal"], build["source"], decoder, *artifacts.values(),
        bindings["profile"]["image"], bindings["profile"]["map"], bindings["whole_boot"], bindings["boot_map"],
        cli.record(Path(__file__)), cli.record(Path(host.__file__)), cli.record(Path(shared.__file__)),
        cli.record(Path(pack.__file__)), cli.record(Path(unpack.__file__)), cli.record(Path(tools.__file__))]
    inputs += s.read(build["source"]["path"])["files"]
    for item in inputs:
        cli.require(cli.record(item["path"]) == item, "prepared source changed")
    groups, outputs = {}, []
    for spec in cli.ERASE_GROUPS.values():
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
        groups[tag] = dict(result="ERASE_ASSETS_VERIFIED", specification=spec, receiver=receiver,
            receiver_bindings=bindings, target=target, target_identity=identity, target_bindings=target_bindings,
            package=package, package_kind="full", header=tools.package_info(blob, spec["receiver"], spec["target_version"]),
            decoded=decoded, decoded_image=target, negatives=negatives)
        outputs.extend((target, package))
        bindings = copy.deepcopy(target_bindings)
    outputs += [cli.record(p) for p in out.glob("*.log")]
    s.write(ROOT / RELATIVE, dict(result="ERASE_ASSETS_VERIFIED", hardware=False, groups=groups, inputs=inputs, outputs=outputs))
    load()
    print("ERASE_ASSETS_VERIFIED", {k: v["package"]["bytes"] for k, v in groups.items()})


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    prepare()
