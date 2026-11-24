"""Reuse verified archival: protect current30248 and preserve inactive30246."""
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_radio_archive as archive
import p34_radio_followup as followup

cli = archive.cli
OUT = followup.AREA / "combined-archive-001"


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    s = cli.Store(ROOT)
    tests = s.read(archive.AREA / "archive-tests/result.json")
    cli.require(tests["result"] == "PASS" and tests["source"] == cli.record(archive.__file__) and
                tests["test"] == cli.record(archive.TEST), "original archive guards changed")
    supervisor = cli.load_module("combined_archive_owner", ROOT / ".cache/p3-4-screening-20260922/supervisor.py")
    if sys.argv[1:] == ["launch"]:
        cli.require(not OUT.exists(), "preserve archive attempt")
        for name in ("intent.json", "result.json", "stop-intent.json", "mkdir-intent.json", "move-intent.json",
                     "capture", "usb", "host"):
            s.checked(OUT / name)
        # These are real measured captures; the invalid scan capture is not selected.
        archive.proof(s, followup.TRIALS / "priority")
        archive.proof(s, archive.radio.TRIALS / "baseline")
        s.write(OUT / "intent.json", dict(source=cli.record(__file__), implementation=cli.record(archive.__file__),
            tests=tests, selected_version=30246, protected_version=30248, no_delete=True, no_ota=True))
        print(supervisor.owned.launch(archive.AREA / "runtime/combined-archive-001", Path(__file__), ["worker"], 600), flush=True)
    else:
        cli.require(sys.argv[1:] == ["worker"] and supervisor.owned.in_job(), "finite archive owner required")
        radio = types.SimpleNamespace(ORDER=("priority",), TRIALS=followup.TRIALS,
            old=types.SimpleNamespace(TRIAL=archive.radio.TRIALS / "baseline"),
            APK=followup.AREA / "apk-g1/apk.json", backend=archive.radio.backend)
        fn = archive.worker
        types.FunctionType(fn.__code__, dict(fn.__globals__, radio=radio), fn.__name__)(s, "priority", OUT)
