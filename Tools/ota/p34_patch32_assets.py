"""Legal 30226 -> 30227 -> 30228 assets using the verified coalescer build."""
import argparse
from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p34_session as cli

ROOT = Path(__file__).resolve().parents[2]
AREA = ROOT / ".cache/p34-patch32"
RELATIVE = ".cache/p34-patch32/assets/result.json"
BUILD_REPORT = ".cache/p34-patch-next/firmware/build.json"
RECEIVER_ASSETS = ".cache/p34-session/speed-window32/assets/result.json"
ADMISSION = AREA / "input-admission.json"


def engine():
    api = cli.load_module("p34_patch32_asset_engine", ROOT / "Tools/ota/p34_patch_assets.py")
    # Only this private adapter changes axes; the legacy engine and build stay intact.
    api.prep = types.SimpleNamespace(**dict(vars(api.prep), AA=30227, AB=30228,
        AA_NAME="3.2.27-p34c", AB_NAME="3.2.28-p34c", Y_ASSETS=ROOT / RECEIVER_ASSETS))
    api.OUT = ROOT / ".cache/p34-patch32/assets"
    api.RELATIVE = RELATIVE
    api.EXTRA_INPUTS = (Path(__file__), ADMISSION)
    return api


def verify_admission(store):
    value = store.read(ADMISSION)
    cli.require(value.get("result") == "PATCH32_INPUTS_ADMITTED" and
                value.get("receiver_version") == 30226 and value.get("versions") == [30227, 30228] and
                value.get("device_operations") == 0, "PATCH32 preparation admission changed")
    previous = cli.completed_full_predecessor(store, value["predecessor"], group=cli.SPEED32_GROUP)
    cli.require(cli.record(ROOT / RECEIVER_ASSETS) == value["receiver_assets"] and
                previous["plan"]["target_bindings"] == store.read(ROOT / RECEIVER_ASSETS)["target_bindings"],
                "PATCH32 does not start from the verified30226 image/Boot")
    return value


def load():
    store = cli.Store(ROOT)
    admission = verify_admission(store)
    api = engine()
    value = api.load()
    cli.require(value["historical_receiver_bindings"] == store.read(ROOT / RECEIVER_ASSETS)["target_bindings"] and
                value["groups"]["bootstrap"]["receiver"] == admission["receiver_version"] and
                value["groups"]["pressure"]["package"]["bytes"] == 1048576,
                "PATCH32 asset lineage/reference length differs")
    return value


def load_for_context(c, specification):
    cli.require(specification in cli.PATCH32_GROUPS.values(), "not an explicit PATCH32 cell")
    verify_admission(cli.Store(ROOT))
    return engine().load_for_context(c, specification)


def prepare(store):
    with store.command_lock():
        if (ROOT / RELATIVE).exists():
            return dict(result=load()["result"], reused=True, device_operations=0)
        cli.require(not AREA.exists(), "preserve partial PATCH32 preparation and nonces")
        run = store.current()
        cli.require(run is not None, "PATCH32 requires the actual completed32 owner")
        previous = cli.completed_full_predecessor(store, cli.current_full_descriptor(store, run), group=cli.SPEED32_GROUP)
        receiver = store.read(ROOT / RECEIVER_ASSETS)
        cli.require(receiver["target_identity"]["version_code"] == 30226 and
                    previous["plan"]["target_bindings"] == receiver["target_bindings"], "current32 asset identity differs")
        for name in ("input-admission.json", "assets", "assets/host", "assets/compact-work/temp_diff.data", "assets/pressure"):
            store.checked(AREA / name)
        store.write(ADMISSION, dict(result="PATCH32_INPUTS_ADMITTED", time=cli.now(), predecessor=previous["descriptor"],
            receiver_assets=cli.record(ROOT / RECEIVER_ASSETS), receiver_version=30226, versions=[30227, 30228],
            device_operations=0, unchanged_boot=True, compact_is_offline_only=True, formal_reference_admitted=False))
        result = engine().prepare()
        load()
        return dict(result, manifest=cli.record(ROOT / RELATIVE), device_operations=0, new_firmware_build=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    cli.require(args.root == ROOT and Path.cwd() == ROOT and sys.flags.isolated and
                sys.flags.no_site and sys.dont_write_bytecode, "isolated explicit project root required")
    import json
    print(json.dumps(prepare(cli.Store(ROOT)) if args.action == "prepare" else
                     dict(result=load()["result"], verified=True)), flush=True)
