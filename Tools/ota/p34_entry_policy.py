"""Run offline device-entry ordering scenarios and record unresolved real gates."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"Tools/ota"))
import p34_install_cost as host


def main():
    cli=host.cli
    cli.require(Path.cwd()==ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode,"isolated root required")
    store=cli.Store(ROOT)
    out=store.checked(ROOT/".cache/p34-entry-policy1")
    cli.require(not out.exists(),"preserve evidence")
    for key in ("HOME","USERPROFILE","APPDATA","LOCALAPPDATA","TEMP","TMP","TMPDIR",
                "XDG_CACHE_HOME","XDG_CONFIG_HOME","XDG_DATA_HOME","PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX","CCACHE_DIR","SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for name in ("tests.log","tests.json","result.json","real-gates.json"):
        store.checked(out/name)
    env=host.environment(store,out)
    test=ROOT/"tests/boot/test_p34_entry_policy.py"
    log=host.command(store,out,"tests",[sys.executable,"-I","-S","-B","-X","utf8",test],env,60)
    cli.require(b"Ran 15 tests" in log and b"\nOK" in log,"missing checks")
    unresolved=["owned current-device acquisition epoch and UID",
        "reviewed actual EEPROM part and timing source",
        "latest possible STOP bound and protocol-idle ownership",
        "independent clock calibration/epoch continuity",
        "safe RAM takeover, DMA/SD and watchdog policy",
        "EEPROM settled observation after any uncertain write",
        "separate physical restore/confirmation entry and safe exit"]
    store.write(out/"real-gates.json",dict(device_execute_ready=False,
        unknown=unresolved,source="offline inventory; no device acquisition performed"))
    inputs=[Path(__file__),test,ROOT/"Tools/ota/recovery_confirm/entry_policy.py",
            ROOT/"Libraries/EEPROM/EEPROM.h",ROOT/"Libraries/EEPROM/EEPROM.cpp",
            ROOT/"Tools/ota/recovery_confirm/confirm.c",ROOT/"Tools/ota/recovery_confirm/observe.c"]
    store.write(out/"result.json",dict(result="OFFLINE_ENTRY_ORDER_SCENARIOS_PASS",tests=15,
        inputs=[cli.record(p) for p in inputs],hardware=False,device_execute_ready=False,
        scope="hypothetical trusted facts; not physical proof or authorization"))
    print("OFFLINE_ENTRY_ORDER_SCENARIOS_PASS tests=15; device_execute_ready=false")


if __name__=="__main__":
    main()
