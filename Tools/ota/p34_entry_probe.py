"""Contained observation-policy self-tests. This runner never loads J-Link."""
import argparse
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host
import p34_session as cli
from recovery_entry.probe import scan_sdk_writes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "explicit root and isolated Python required")
    store = cli.Store(ROOT)
    out = store.checked(args.output_dir)
    cli.require(not out.exists(), "preserve existing evidence")
    inputs = [ROOT / name for name in (
        "Tools/ota/recovery_entry/probe.py", "Tools/ota/p34_entry_probe.py",
        "tests/boot/test_p34_entry_probe.py", "Tools/ota/p34_session.py",
        "Tools/ota/p34_install_cost.py",
        ".agents/skills/e-track-flutter-debug/scripts/host_io.py",
    )]
    logs = sorted((ROOT / ".cache/p34-early-identity1").glob("*/sdk.log"))
    cli.require(len(logs) == 5, "five historical SDK logs required")
    bindings = [cli.record(p) for p in [*inputs, *logs]]
    outputs = [out / name for name in ("tests.log", "tests.json", "result.json")]
    outputs += [out / "source" / p.relative_to(ROOT) for p in inputs]
    outputs += [out / "host" / key.lower() for key in (
        "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
        "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
        "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR")]
    for path in outputs:
        store.checked(path)
    env = host.environment(store, out)
    for path in inputs:
        store.raw(out / "source" / path.relative_to(ROOT), path.read_bytes())
    data = host.command(store, out, "tests", [sys.executable, "-I", "-S", "-B", "-X", "utf8",
        ROOT / "tests/boot/test_p34_entry_probe.py", "-v"], env, 60)
    match = re.search(rb"Ran (\d+) tests? in .*\r?\n\r?\nOK\b", data)
    cli.require(match is not None, "test count/success missing")
    counts = [scan_sdk_writes(p.read_text(errors="strict")) for p in logs]
    cli.require([cli.record(p) for p in [*inputs, *logs]] == bindings, "input drift")
    store.write(out / "result.json", dict(result="PROBE_POLICY_HOST_PASS",
        tests=int(match[1]), hardware=False, native_dll_loaded=False,
        native_transport_qualified=False, device_execute_ready=False,
        historical_cpu_write_calls=sum(len(v["writes"]) for v in counts),
        sdk_write_audit_passed=False, transient_debug_state_proven_unchanged=False,
        inputs=bindings, outputs=[cli.record(p) for p in outputs if p.is_file()]))
    print("PROBE_POLICY_HOST_PASS", int(match[1]), "tests; no DLL/device access")


if __name__ == "__main__":
    main()
