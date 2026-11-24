"""Separate fixed-signer artifact receipts for the verified recorder correction."""
import json
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
SHA = "24ce23842d80241731eee335e60688447a55380b"


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_radio_validation.py"))["runtime"]()
    original = b.OUT
    b.OUT = b.host.OUT = b.checked(original / "recorder-fix")
    b.unchanged_original = lambda: b.require(b.original_state() ==
        json.loads((original / "prepared.json").read_bytes())["original"], "original worktree changed")
    def latest(name):
        paths = sorted(original.glob(name + "-*.json"))
        b.require(bool(paths), "missing original validation receipt")
        return json.loads(paths[-1].read_bytes())
    b.latest = latest
    return b


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("explicit root and isolated Python required")
    entry = runpy.run_path(str(ROOT / "Tools/ota/p34_connect_artifacts.py"))["main"]
    def load(path):
        path = Path(path)
        if path == ROOT / "Tools/ota/p34_connect_validation.py":
            return dict(runtime=runtime)
        if path == ROOT / "Tools/ota/p34_signing_artifacts.py":
            return runpy.run_path(str(path))
        raise RuntimeError("unexpected recorder artifact loader")
    entry.__globals__.update(SHA=SHA, runpy=types.SimpleNamespace(run_path=load))
    entry()
