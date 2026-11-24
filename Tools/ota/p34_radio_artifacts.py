"""Fixed-signer APK dispatch/collection for the tested radio-policy revision."""
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
SHA = "254e78507d27aedc636cca3614272003e67bd369"


def main():
    entry = runpy.run_path(str(ROOT / "Tools/ota/p34_connect_artifacts.py"))["main"]
    def load(path):
        path = Path(path)
        if path == ROOT / "Tools/ota/p34_connect_validation.py":
            return runpy.run_path(str(ROOT / "Tools/ota/p34_radio_validation.py"))
        if path == ROOT / "Tools/ota/p34_signing_artifacts.py":
            return runpy.run_path(str(path))
        raise RuntimeError("unexpected radio artifact loader")
    entry.__globals__.update(SHA=SHA, runpy=types.SimpleNamespace(run_path=load))
    entry()


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    main()
