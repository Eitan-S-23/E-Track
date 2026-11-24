"""Finite detached owners for verified artifact retrieval and in-place update."""
import argparse
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

AREA = ROOT / ".cache/p34-connect-fix/runtime"
OPERATIONS = {
    "collect": ("p34_connect_artifacts.py", ["collect", "--attempt", "1"], 2400),
    "install": ("p34_connect_install.py", [], 900),
    "install-retry": ("p34_connect_install.py", ["--attempt", "2"], 900),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("launch", "worker"))
    parser.add_argument("operation", choices=tuple(OPERATIONS))
    args = parser.parse_args()
    s = cli.Store(ROOT)
    out = s.checked(AREA / (args.operation + "-001"))
    script, extra, seconds = OPERATIONS[args.operation]
    source = ROOT / "Tools/ota" / script
    supervisor = cli.load_module("connect_repair_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    intent = s.checked(AREA / (args.operation + "-intent.json"))
    if args.mode == "launch":
        cli.require(not intent.exists() and not out.exists(), "operation already owned; inspect its receipt")
        dependencies = [source, ROOT / "Tools/ota/p34_connect_validation.py",
                        ROOT / "Tools/ota/p34_signing_artifacts.py"]
        s.write(intent, dict(time=cli.now(), operation=args.operation, sources=[cli.record(p) for p in dependencies]))
        print(supervisor.owned.launch(out, Path(__file__), ["worker", args.operation], seconds), flush=True)
    else:
        cli.require(supervisor.owned.in_job(), "finite owned worker required")
        binding = s.read(intent)
        cli.require(binding["operation"] == args.operation and
                    all(cli.record(r["path"]) == r for r in binding["sources"]), "worker source drift")
        sys.argv = [str(source), *extra]
        runpy.run_path(str(source), run_name="__main__")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    main()
