"""Hash-verified project-contained extraction of the locked Android BLE plugin."""
from pathlib import Path, PurePosixPath
import hashlib
import io
import runpy
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / ".cache/p34-phy"
SHA = "9723dd4ba7dcc3f27f8202e1159a302eb4cdb88ae482bb8e0dd733b82230a258"
URL = "https://pub.dev/api/archives/flutter_blue_plus_android-4.0.5.tar.gz"


def main():
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError("isolated explicit root required")
    guard = runpy.run_path(str(ROOT / ".agents/skills/e-track-flutter-debug/scripts/host_io.py"))
    check = lambda path: guard["checked_output"](ROOT, path)
    dest = check(OUT / "src/app/bluetooth_flutter_Trace/vendor/flutter_blue_plus_android")
    archive = check(OUT / "flutter_blue_plus_android-4.0.5.tar.gz")
    receipt = check(OUT / "vendor.json")
    if dest.exists() or archive.exists() or receipt.exists() or not (OUT / "prepared.json").is_file():
        raise RuntimeError("require fresh vendor outputs and prepared source")
    # Use the host's working HTTPS/proxy stack, retaining TLS verification.
    response = subprocess.run(["curl.exe", "-q", "--fail", "--silent", "--show-error",
        "--max-time", "45", "--max-filesize", "8388608", URL], cwd=ROOT,
        capture_output=True, timeout=50, creationflags=subprocess.CREATE_NO_WINDOW)
    if response.returncode:
        raise RuntimeError("dependency HTTPS download failed: " + str(response.returncode))
    raw = response.stdout
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise RuntimeError("upstream dependency digest mismatch")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as source:
        members = source.getmembers()
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or ":" in member.name or
                    "\\" in member.name or not (member.isdir() or member.isfile()) or
                    member.name.casefold() in names):
                raise RuntimeError("unsafe dependency member")
            names.add(member.name.casefold())
            check(dest / Path(*path.parts))
        with archive.open("xb") as stream:
            stream.write(raw)
        files = {}
        for member in members:
            path = check(dest / member.name)
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                data = source.extractfile(member).read()
                with path.open("xb") as stream:
                    stream.write(data)
                files[member.name] = hashlib.sha256(data).hexdigest()
    guard["write_json"](ROOT, receipt, dict(url=URL, sha256=SHA, files=files,
        destination=str(dest), hardware=False))
    print("VERIFIED_VENDOR", len(files), SHA)


if __name__ == "__main__":
    main()
