"""Retest startup scheduling; retain unaffected original development results."""
import ast
import inspect
import os
from pathlib import Path
import re
import runpy
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host

AREA = ROOT / ".cache/p34-cost/measure-preparation"
OUT = AREA / "tests"
BASE = ROOT / ".cache/p34-cost/network-fix/tests/coverage.json"
NEW = "test_cold_start_waits_for_service_without_spending_cell_or_weakening_timeout"


def child():
    original = unittest.TextTestRunner.run
    def flatten(suite):
        for t in suite:
            if isinstance(t, unittest.TestSuite):
                yield from flatten(t)
            else:
                yield t
    def run(runner, suite):
        tests = list(flatten(suite))
        selected = [t for t in tests if any(s in inspect.getsource(getattr(type(t), t._testMethodName))
                                          for s in ("cli.start(", "cli.wait_until("))]
        cli.require(len(tests) == 357 and any(t._testMethodName == NEW for t in selected), "unexpected startup selection")
        cli.Store(ROOT).write(OUT / "selection.json", dict(all_ids=[t.id() for t in tests], executed_ids=[t.id() for t in selected]))
        return original(runner, unittest.TestSuite(selected))
    unittest.TextTestRunner.run = run
    runpy.run_path(str(ROOT / "tests/ota/test_p34_session.py"), run_name="__main__")


def run():
    s = cli.Store(ROOT)
    cli.require(not OUT.exists(), "preserve test attempt")
    before = AREA / "before"
    snapshots = s.read(before / "result.json")
    for item in snapshots["files"]:
        cli.require(cli.record(item["path"]) == item, "snapshot changed")
    base = s.read(BASE)
    changed = {Path(i["path"]).name for i in base["sources"] if cli.record(i["path"]) != i}
    cli.require(changed == {"p34_session.py", "test_p34_session.py"}, "unexpected session source changes")
    old = (before / "p34_session.py").read_text(encoding="utf-8")
    expected = old.replace("NETWORK_SUPERVISOR_SECONDS = 5480\n", "NETWORK_SUPERVISOR_SECONDS = 5480\nNETWORK_READY_WAIT_SECONDS = 900\n")
    expected = expected.replace("wait_until(network_ready, seconds=450)", "wait_until(network_ready, seconds=NETWORK_READY_WAIT_SECONDS)")
    cli.require(expected == (ROOT / "Tools/ota/p34_session.py").read_text(encoding="utf-8"), "non-wait CLI change")
    a = ast.parse((before / "test_p34_session.py").read_bytes())
    b = ast.parse((ROOT / "tests/ota/test_p34_session.py").read_bytes())
    for node in ast.walk(b):
        if isinstance(node, ast.ClassDef):
            node.body = [n for n in node.body if not isinstance(n, ast.FunctionDef) or n.name != NEW]
    cli.require(ast.dump(a) == ast.dump(b), "old test changed")
    marker = "    c = api.installed_context(out)"
    old_archive = (before / "p34_cost_archive.py").read_text(encoding="utf-8").split(marker, 1)[1].split('\n\nif __name__', 1)[0]
    new_archive = (ROOT / "Tools/ota/p34_cost_archive.py").read_text(encoding="utf-8").split(marker, 1)[1].split('\n\nif __name__', 1)[0]
    old_archive = re.sub(r"\bCAPTURE\b", "selected_capture", old_archive)
    old_archive = re.sub(r"\bPROTECTED\b", "protected_capture", old_archive).replace("current App not exact completed30238", "current App not exact completed target")
    cli.require(old_archive == new_archive, "archive byte/path/lifecycle guards changed")
    archive = cli.load_module("cost_measure_archive_test", ROOT / "Tools/ota/p34_cost_archive.py")
    for current, message in (("wrong", "current owner changed"), ("20260930T163130-3100", "bound backend")):
        with mock.patch.object(cli, "Store", return_value=s), mock.patch.object(s, "current", return_value=current), \
                mock.patch.object(cli, "verify_tests", return_value={}), \
                mock.patch.object(cli, "backend", side_effect=RuntimeError("bound backend")) as backend:
            try:
                archive.run(measure=True)
            except RuntimeError as e:
                cli.require(message in str(e), "wrong archive gate")
            else:
                raise RuntimeError("archive test executed")
            if current != "wrong":
                cli.require(backend.call_args.args[1:] == (s.base / "profile-cost-bootstrap-v2.json", "cost-bootstrap"), "wrong measure bindings")
            else:
                backend.assert_not_called()
    cli.require(not (ROOT / ".cache/p34-cost/archive-30238").exists(), "archive guard test wrote output")
    env = host.environment(s, OUT)
    env["P34_TEST_OUT"] = str(OUT)
    s.write(OUT / "scope.json", dict(before=cli.record(before / "result.json"), prior=cli.record(BASE),
        unchanged_old_test_AST=True, change="parent service readiness wait450 to900 only; no service/cell/transfer deadline change",
        archive_guards_unchanged=True, archive_binding_checks=2, archive_source=cli.record(archive.__file__)))
    host.command(s, OUT, "runner", [sys.executable, "-I", "-S", "-B", "-X", "utf8", __file__, "child"], env, 900)
    result, selection = s.read(OUT / "result.json"), s.read(OUT / "selection.json")
    cli.require(result["passed"] and result["tests"] == len(selection["executed_ids"]) and result["skipped"] == 0, "startup tests failed")
    old_ids = set(base["fresh_ids"] + base["reused_ids"])
    cli.require(set(selection["all_ids"]) - old_ids == {"__main__.SessionTests." + NEW}, "unaccounted suite change")
    reused = sorted(set(selection["all_ids"]) - set(selection["executed_ids"]))
    cli.require(set(reused) <= old_ids, "test has no prior origin")
    value = dict(result, tests=357, executed_tests=result["tests"], reused_tests=len(reused),
        fresh_ids=selection["executed_ids"], reused_ids=reused, prior_coverage=cli.record(BASE),
        executed=cli.record(OUT / "result.json"), original_log=cli.record(OUT / "unittest.log"),
        proof=cli.record(OUT / "scope.json"), scope="Development only; startup scheduling changed, unaffected original cases reused")
    s.write(OUT / "coverage.json", value)
    s.write(s.base / "tests/latest.json", value, replace=True)
    print("STARTUP_WAIT_PASS", result["tests"], "executed", len(reused), "reused")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    if sys.argv[1:] == ["child"]:
        child()
    else:
        cli.require(not sys.argv[1:], "unexpected arguments")
        run()
