"""Rerun only the two host-lock collisions after the owner closed."""
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

AREA = ROOT / ".cache/p34-erase"
PREVIOUS = AREA / "session-tests-r2"
OUT = AREA / "session-tests-r3"
FAILED = {
    "p34_speed32_tests.RetirementRecoveryTests.test_recovery_flag_does_not_enable_other_commands_or_groups",
    "p34_speed32_tests.RetirementRecoveryTests.test_recovery_token_cannot_be_reused_after_current_advances",
}


def child():
    original = unittest.TextTestRunner.run
    def flatten(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from flatten(test)
            else:
                yield test
    def run(runner, suite):
        tests = list(flatten(suite))
        picked = [t for t in tests if t.id() in FAILED]
        cli.require(len(tests) == 369 and {t.id() for t in picked} == FAILED, "wrong retry scope")
        return original(runner, unittest.TestSuite(picked))
    unittest.TextTestRunner.run = run
    runpy.run_path(str(ROOT / "tests/ota/test_p34_session.py"), run_name="__main__")


def run():
    s = cli.Store(ROOT)
    cli.require(not s.checked(OUT).exists() and not (s.base / "command.lock").exists(), "preserve attempt or active command")
    result = s.read(PREVIOUS / "result.json")
    selection = s.read(PREVIOUS / "selection.json")
    log = (PREVIOUS / "unittest.log").read_text(encoding="utf-8")
    cli.require(not result["passed"] and result["tests"] == 140 and result["errors"] == 2 and
                result["failures"] == result["skipped"] == 0, "unexpected prior failure")
    passed = set(re.findall(r"^\w+ \(([^)]+)\) \.\.\. ok$", log, re.M))
    failed = set(re.findall(r"^\w+ \(([^)]+)\) \.\.\. ERROR$", log, re.M))
    cli.require(failed == FAILED and len(passed) == 138 and passed | failed == set(selection["executed_ids"]),
                "unaccounted prior result")
    errors = log.split("======================================================================")[1:]
    cli.require(len(errors) == 2 and all("FileExistsError:" in e and "command.lock" in e for e in errors),
                "not the diagnosed host-lock collision")
    for item in result["sources"]:
        cli.require(cli.record(item["path"]) == item, "source changed after original execution")
    base = s.read(AREA / "integration-before/latest.json")
    old_ids = set(base["fresh_ids"] + base["reused_ids"])
    new_ids = set(selection["all_ids"]) - old_ids
    cli.require(len(new_ids) == 12 and all(i.startswith(("p34_erase_suite.", "p34_historical_suite.")) for i in new_ids),
                "suite scope changed")
    reused = sorted(set(selection["all_ids"]) - set(selection["executed_ids"]))
    cli.require(len(reused) == 229 and set(reused) <= old_ids, "missing original PASS")
    env = host.environment(s, OUT)
    env["P34_TEST_OUT"] = str(OUT)
    s.write(OUT / "scope.json", dict(prior_result=cli.record(PREVIOUS / "result.json"),
        prior_log=cli.record(PREVIOUS / "unittest.log"), original_scope=cli.record(PREVIOUS / "scope.json"),
        rerun_ids=sorted(FAILED), unchanged_current_pass_ids=sorted(passed),
        reason="Concurrent prepare-patch held the actual command.lock. Owner exited normally; no lock removal or guard change."))
    host.command(s, OUT, "runner", [sys.executable, "-I", "-S", "-B", "-X", "utf8", __file__, "child"], env, 180)
    fresh = s.read(OUT / "result.json")
    cli.require(fresh["passed"] and fresh["tests"] == 2 and not fresh["skipped"] and fresh["sources"] == result["sources"],
                "retry did not establish exact PASS")
    value = dict(fresh, tests=369, executed_tests=140, reused_tests=229,
        fresh_ids=selection["executed_ids"], reused_ids=reused,
        prior_coverage=cli.record(AREA / "integration-before/latest.json"),
        current_executed=cli.record(PREVIOUS / "result.json"), executed=cli.record(OUT / "result.json"),
        original_log=cli.record(OUT / "unittest.log"), proof=cli.record(OUT / "scope.json"),
        scope="Development coverage:138 current original PASS plus2 isolated lock retries,229 unchanged prior PASS; not369 re-executed")
    s.write(OUT / "coverage.json", value)
    s.write(s.base / "tests/latest.json", value, replace=True)
    print("ERASE_SESSION_PASS current140 reused229; only2 lock-collision retries")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    if sys.argv[1:] == ["child"]:
        child()
    else:
        cli.require(not sys.argv[1:], "unexpected arguments")
        run()
