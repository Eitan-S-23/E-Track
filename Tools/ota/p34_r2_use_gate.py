"""Build an offline VTOR profile and finite image-role inventory, never flash."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host
import p34_r2_vtor_policy as policy

AREA = ROOT / ".cache/p34-early-use1"
R2 = ROOT / ".cache/p34-early-usb-r2"


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    store.checked(AREA)
    cli.require(not AREA.exists(), "preserve use-gate evidence")
    for name in ("profile.json", "images.json", "result.json", "policy-tests.log", "policy-tests.json"):
        store.checked(AREA / name)
    for key in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir", "xdg_cache_home",
                "xdg_config_home", "xdg_data_home", "pythonuserbase", "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        store.checked(AREA / "host" / key)
    paths = [Path(__file__), Path(policy.__file__), Path(host.__file__), Path(cli.__file__),
        Path(policy.validate.__file__), R2 / "prepared.json", R2 / "validation.json",
        R2 / "two-msp1/result.json", R2 / "on/symbols.log",
        ROOT / ".cache/p34-app-handoff/result.json", ROOT / ".cache/p34-bc-target/result.json",
        ROOT / ".cache/p34-boot/activation/after/boot.bin",
        ROOT / "Tools/ota/p34_full_trace.py", ROOT / "Tools/ota/p34_boot_device.py",
        ROOT / "Tools/ota/baud_interruption.py", R2 / "f/USER/main.cpp"]
    paths += [R2 / "on/b/app-gcc" / ("X-Track-App-GCC"+s) for s in (".bin", ".elf", ".map")]
    prepared, validation, oldapp, oldboot = (store.read(paths[i]) for i in (5, 6, 9, 10))
    for record in prepared["sources"]+prepared["implementation"]+validation["inputs"]+oldapp["inputs"]+[oldboot["inputs"]]:
        cli.require(cli.record(record["path"]) == record, "input evidence drift")
    records = [cli.record(p) for p in paths]
    backup = cli.record(paths[11])
    cli.require(backup["bytes"] == 65536 and backup["sha256"] ==
                "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4", "full Boot backup drift")
    raw = paths[-3].read_bytes()
    profile = policy.profile(raw, policy.validate.parse_symbols(paths[8].read_text()), prepared["entries"])
    store.write(AREA / "profile.json", profile)
    images = [dict(role="isolated_candidate_source", identity=cli.record(paths[-3]),
        elf=cli.record(paths[-2]), map=cli.record(paths[-1]), early_analysis="R2-only conditional EARLY-03 closure",
        vtor_profile=cli.record(AREA / "profile.json"), ota_version=None, package=None,
        deployable=False, recovery_route="Not assigned; raw linked image is not a finalized OTA candidate")]
    for name, group in oldapp["groups"].items():
        rec = group["image"]
        cli.require(cli.record(rec["path"]) == rec, "old App image drift")
        images.append(dict(role="last_recorded_App" if name == "measure" else "historical_predecessor",
            version=group["version"], identity=rec, physical_current_verified_this_batch=False,
            early_analysis="NOT_COVERED: old initialization gap remains",
            recovery_route="Historical executable only; not an approved early-vector-safe recovery image"))
    images += [dict(role="physical_backup_App", identity=None, status="UNKNOWN_NOT_READ",
                    recovery_route="Must bind actual backup payload before any device plan; 30274 is not proof"),
               dict(role="selected_recovery_App", identity=None, status="NOT_SELECTED",
                    recovery_route="Requires exact finalized image, matching artifacts and approved restore plan"),
               dict(role="known_good_full_Boot_backup", identity=backup, status="PRESERVED_NOT_DEVICE_READ_THIS_BATCH",
                    recovery_route="Exact full 65536B restore only after device/recovery authorization; never pad compact BIN")]
    store.write(AREA / "images.json", dict(schema="p34-early-finite-images/v1", images=images,
        boot_variants_evidence=cli.record(paths[10]), hardware=False, device_use_ready=False,
        unresolved=["finalized candidate/package identity", "actual physical backup identity",
                    "approved recovery App identity", "live collector integration and reset-generation binding",
                    "device replacement/recovery authorization and finite observation plan"]))
    env = host.environment(store, AREA)
    data = host.command(store, AREA, "policy-tests",
                        [sys.executable, "-I", "-S", "-B", "-X", "utf8", Path(policy.__file__), "--selftest"], env, 60)
    match = re.fullmatch(rb"R2_VTOR_POLICY_PASS cases=(\d+)\r?\n", data)
    cli.require(match is not None, "policy test summary missing")
    cli.require(records == [cli.record(p) for p in paths], "inputs changed during checks")
    outputs = [cli.record(AREA / n) for n in ("profile.json", "images.json", "policy-tests.json", "policy-tests.log")]
    store.write(AREA / "result.json", dict(result="EARLY04_OFFLINE_POLICY_AND_IMAGE_INVENTORY", inputs=records,
        outputs=outputs, host_cases=int(match[1]), hardware=False, independent_acceptance=False,
        compatibility=dict(early_main="unchanged strict primary VTOR check",
            legacy_trace="unchanged; rejects R2 runtime VTOR as expected",
            legacy_boot_probe="unchanged; tied to historical App hash and primary address",
            legacy_interruption_gate="unchanged; primary-only historical snapshot",
            new_policy="opt-in offline image/table classifier; not yet wired into a live collector"),
        gate_status="OPEN_PENDING_FINAL_IMAGE_IDENTITIES_AND_COLLECTOR_INTEGRATION"))
    print("EARLY04_OFFLINE_POLICY_AND_IMAGE_INVENTORY", "host_cases", int(match[1]), "device_use_ready=False")


if __name__ == "__main__":
    main()
