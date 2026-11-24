"""Reuse the verified PHY artifact route for the isolated recorder repair."""
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]


def main():
    entry = runpy.run_path(str(ROOT / "Tools/ota/p34_phy_artifacts.py"))["main"]
    original = runpy.run_path
    def load(path):
        if Path(path) == ROOT / "Tools/ota/p34_phy_validation.py":
            return original(str(ROOT / "Tools/ota/p34_phy_logfix_validation.py"))
        return original(path)
    entry.__globals__["runpy"] = SimpleNamespace(run_path=load)
    entry()


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    main()
