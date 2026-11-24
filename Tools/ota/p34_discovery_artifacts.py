"""Reuse fixed-signer artifact gates for the exact reboot-discovery revision."""
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
SHA = "89fee42f548e99eb5bc437aa736d2e9cc8ddf5de"


def main():
    entry = runpy.run_path(str(ROOT / "Tools/ota/p34_connect_artifacts.py"))["main"]
    def load(path):
        path = Path(path)
        if path == ROOT / "Tools/ota/p34_connect_validation.py":
            return runpy.run_path(str(ROOT / "Tools/ota/p34_discovery_validation.py"))
        if path == ROOT / "Tools/ota/p34_signing_artifacts.py":
            return runpy.run_path(str(path))
        raise RuntimeError("unexpected artifact loader: " + str(path))
    entry.__globals__.update(SHA=SHA, runpy=types.SimpleNamespace(run_path=load))
    entry()


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    main()
