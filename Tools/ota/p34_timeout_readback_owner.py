"""Own a finite readback after the terminal-host launch ended before MCU contact."""
import argparse
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-reconnect/timeout-30243/readback-recovery"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    for p in (AREA, AREA / "runtime", AREA / "readback-001"):
        s.checked(p)
    supervisor = cli.load_module("timeout_readback_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if args.mode == "launch":
        old = AREA.parent / "readback-001"
        cli.require({p.name for p in old.iterdir()} == {"intent.json"}, "earlier readback may have contacted MCU")
        cli.require(not AREA.exists(), "owned recovery already reserved")
        s.write(AREA / "intent.json", dict(time=cli.now(), original=cli.record(old / "intent.json"),
            source=cli.record(__file__), original_result="host ended before MCU outputs; not a failed device operation"))
        print(supervisor.owned.launch(AREA / "runtime", Path(__file__), ["worker"], 900), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "readback worker requires a finite owner")
        module = runpy.run_path(str(ROOT / "Tools/ota/p34_reconnect_timeout.py"))
        module["readback"].__globals__["AREA"] = AREA
        module["readback"](s)


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    main()
