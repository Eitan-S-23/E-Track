"""Complete the timed-out development suite without losing its original PASS records."""
import os
from pathlib import Path
import re
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host

PRIOR = ROOT / ".cache/p34-session/tests/1790867959001173300"
OUT = ROOT / ".cache/p34-reconnect/session-tests-r2"


def completed_ids():
    text = (PRIOR / "unittest.log").read_text(encoding="utf-8")
    cli.require("... FAIL" not in text and "... ERROR" not in text and "... skipped" not in text,
                "original failure or skipped test cannot be reused")
    ids = re.findall(r"(?m)^\S+ \(([^)]+)\) \.\.\. ok$", text)
    cli.require(len(ids) == len(set(ids)) == 354, "original PASS set changed")
    return set(ids)


def child():
    passed = completed_ids()
    original = unittest.TextTestRunner.run
    def flatten(suite):
        for case in suite:
            if isinstance(case, unittest.TestSuite):
                yield from flatten(case)
            else:
                yield case
    def run(runner, suite):
        tests = list(flatten(suite))
        ids = [t.id() for t in tests]
        cli.require(len(ids) == len(set(ids)) == 375 and passed < set(ids), "suite identity changed")
        remaining = [t for t in tests if t.id() not in passed]
        cli.Store(ROOT).write(OUT / "selection.json", dict(all_ids=ids, fresh_ids=[t.id() for t in remaining],
            prior_pass_ids=sorted(passed)))
        return original(runner, unittest.TestSuite(remaining))
    unittest.TextTestRunner.run = run
    runpy.run_path(str(ROOT / "tests/ota/test_p34_session.py"), run_name="__main__")


def main():
    s = cli.Store(ROOT)
    cli.require(not s.checked(OUT).exists(), "preserve residual test attempt")
    prior = s.read(PRIOR / "timeout.json")
    cli.require(prior["result"] == "HOST_TEST_TIMEOUT" and prior["device_operations"] == 0,
                "only the original host timeout is admitted")
    completed_ids()
    env = host.environment(s, OUT)
    env["P34_TEST_OUT"] = str(OUT)
    # The source files were not changed during the first invocation. Freeze the
    # same current bytes before the residual invocation; this is development only.
    files = [ROOT / "Tools/ota/p34_session.py", ROOT / "Tools/ota/p34_session_backend.py",
             ROOT / "Tools/ota/p34_reconnect_profile.py", ROOT / "tests/ota/test_p34_session.py",
             ROOT / "tests/ota/test_p34_reconnect.py"]
    sources = [cli.record(p) for p in files]
    s.write(OUT / "scope.json", dict(prior_log=cli.record(PRIOR / "unittest.log"),
        timeout=cli.record(PRIOR / "timeout.json"), unchanged_during_original_invocation=True,
        sources=sources, prior_passes=354, remaining=21, independent_acceptance=False))
    host.command(s, OUT, "runner", [sys.executable, "-I", "-S", "-B", "-X", "utf8", __file__, "child"], env, 900)
    result, selection = s.read(OUT / "result.json"), s.read(OUT / "selection.json")
    cli.require(result["passed"] and result["tests"] == 21 and result["skipped"] == 0 and
                all(cli.record(p) == r for p, r in zip(files, sources)), "residual tests failed or source drift")
    value = dict(result, tests=375, executed_tests=21, reused_tests=354,
        fresh_ids=selection["fresh_ids"], reused_ids=selection["prior_pass_ids"],
        prior_log=cli.record(PRIOR / "unittest.log"), prior_timeout=cli.record(PRIOR / "timeout.json"),
        executed=cli.record(OUT / "result.json"), proof=cli.record(OUT / "scope.json"),
        scope="Development only: 354 original PASS records plus 21 residual tests; timeout preserved")
    s.write(OUT / "coverage.json", value)
    s.write(s.base / "tests/latest.json", value, replace=True)
    print("RECONNECT_SESSION_PASS 375 (354 original + 21 residual)")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    child() if sys.argv[1:] == ["child"] else main()
