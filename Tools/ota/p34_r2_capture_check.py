"""Run the new capture tests with contained original logs and input bindings."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host

AREA = ROOT / ".cache/p34-early-capture1"


def main():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated project root required")
    store = cli.Store(ROOT)
    store.checked(AREA)
    cli.require(not AREA.exists(), "preserve capture test evidence")
    for name in ("result.json", "host-tests.json", "host-tests.log"):
        store.checked(AREA / name)
    for name in ("home", "userprofile", "appdata", "localappdata", "temp", "tmp", "tmpdir", "xdg_cache_home",
                 "xdg_config_home", "xdg_data_home", "pythonuserbase", "pythonpycacheprefix", "ccache_dir", "sccache_dir"):
        store.checked(AREA / "host" / name)
    paths = [Path(__file__), Path(cli.__file__), Path(host.__file__),
        ROOT / "Tools/ota/p34_r2_vtor_capture.py", ROOT / "Tools/ota/p34_r2_vtor_capture_tests.py",
        ROOT / "Tools/ota/p34_r2_vtor_policy.py", ROOT / ".cache/p34-early-use1/profile.json",
        ROOT / ".cache/p34-early-use1/result.json",
        ROOT / ".cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.bin"]
    records = [cli.record(p) for p in paths]
    old = store.read(paths[7])
    for record in old["inputs"]+old["outputs"]:
        cli.require(cli.record(record["path"]) == record, "use-gate evidence drift")
    env = host.environment(store, AREA)
    output = host.command(store, AREA, "host-tests",
                          [sys.executable, "-I", "-S", "-B", "-X", "utf8", paths[4]], env, 60)
    match = re.fullmatch(rb"R2_VTOR_CAPTURE_PASS cases=(\d+)\r?\n", output)
    cli.require(match is not None, "missing capture test summary")
    cli.require(records == [cli.record(p) for p in paths], "capture test inputs changed")
    store.write(AREA / "result.json", dict(result="R2_READ_ONLY_CAPTURE_HOST_TESTED", inputs=records,
        outputs=[cli.record(AREA / n) for n in ("host-tests.json", "host-tests.log")],
        cases=int(match[1]), hardware=False, independent_acceptance=False,
        native_route_validated=False, boot_generation_proven=False, device_use_ready=False,
        remaining=["authorized native reader and its enforced per-call timeout", "boot-generation and non-VTOR admission checks",
                   "finalized candidate/recovery profile", "actual backup identity"]))
    print("R2_READ_ONLY_CAPTURE_HOST_TESTED cases", int(match[1]))


if __name__ == "__main__":
    main()
