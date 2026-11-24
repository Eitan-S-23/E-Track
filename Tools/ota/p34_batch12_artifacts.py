"""One fixed-signer development APK for the batch3/batch12 comparison."""
from pathlib import Path
import runpy
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
SHA = "c5a8c53195bcda43e3ae060f7ce5e8007a4cf6ae"


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_batch12_validation.py"))["runtime"]()
    save = b.save
    def bound_save(path, value):
        if path == "apk-g1/intent.json":
            value = dict(value, purpose="bounded batch12 sender; same package and fixed signer")
        return save(path, value)
    b.save = bound_save
    return b


if __name__ == "__main__":
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    entry = runpy.run_path(str(ROOT / "Tools/ota/p34_connect_artifacts.py"))["main"]
    def load(path):
        path = Path(path)
        if path == ROOT / "Tools/ota/p34_connect_validation.py":
            return dict(runtime=runtime)
        if path == ROOT / "Tools/ota/p34_signing_artifacts.py":
            return runpy.run_path(str(path))
        raise RuntimeError("unexpected batch12 artifact dependency")
    entry.__globals__.update(SHA=SHA, runpy=types.SimpleNamespace(run_path=load))
    entry()
