"""Repair metadata only and retest the real FULL service contract."""
import ast
import copy
import os
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host
import p34_cost_assets as assets

AREA = ROOT / ".cache/p34-cost/network-fix"
OUT = AREA / "tests"
BASE = ROOT / ".cache/p34-cost/session-tests/coverage.json"


def manifest(s):
    original = ROOT / ".cache/p34-cost/assets/result.json"
    value = s.read(original)
    for item in value["inputs"] + value["outputs"]:
        path = Path(item["path"])
        actual = cli.record(AREA / path.name) if path == Path(assets.__file__) else cli.record(path)
        cli.require((actual["sha256"], actual["bytes"]) == (item["sha256"], item["bytes"]), "old asset input changed")
    revised = copy.deepcopy(value)
    for spec in cli.COST_GROUPS.values():
        g = revised["groups"][spec["asset_group"]]
        expected = dict(g["specification"], served_name=spec["served_name"], assets=spec["assets"])
        cli.require(expected == spec, "non-filename specification change")
        g["specification"] = expected
    revised["inputs"] = [cli.record(AREA / "p34_cost_assets.py") if Path(i["path"]) == Path(assets.__file__) else i
                         for i in value["inputs"]]
    revised["inputs"] += [cli.record(original), cli.record(assets.__file__)]
    s.write(ROOT / assets.RELATIVE, revised)
    assets.load()


def child():
    original = unittest.TextTestRunner.run
    def flatten(suite):
        for t in suite:
            if isinstance(t, unittest.TestSuite):
                yield from flatten(t)
            else:
                yield t
    def selected(runner, suite):
        all_tests = list(flatten(suite))
        tests = [t for t in all_tests if t.id().startswith("p34_cost_suite.Tests.")]
        cli.require(len(all_tests) == 356 and len(tests) == 5, "unexpected test selection")
        cli.Store(ROOT).write(OUT / "selection.json", dict(all_ids=[t.id() for t in all_tests],
            executed_ids=[t.id() for t in tests]))
        return original(runner, unittest.TestSuite(tests))
    unittest.TextTestRunner.run = selected
    runpy.run_path(str(ROOT / "tests/ota/test_p34_session.py"), run_name="__main__")


def test(s):
    base = s.read(BASE)
    snapshots = s.read(AREA / "before.json")
    for i in snapshots["files"]:
        cli.require(cli.record(i["path"]) == i, "snapshot changed")
    changed = {Path(i["path"]).name for i in base["sources"] if cli.record(i["path"]) != i}
    cli.require(changed == {"p34_session.py", "p34_cost_assets.py", "test_p34_cost_assets.py"}, "scope changed")
    for name, replacements in (
        ("p34_session.py", (("p34-cost-bootstrap.etu", "p34-cost-bootstrap-full.etu"),
                            ("p34-cost-measure.etu", "p34-cost-measure-full.etu"),
                            ("p34-cost/assets/result.json", "p34-cost/assets/result-v2.json"))),
        ("p34_cost_assets.py", (("p34-cost/assets/result.json", "p34-cost/assets/result-v2.json"),))):
        text = (AREA / name).read_text(encoding="utf-8")
        for before, after in replacements:
            text = text.replace(before, after)
        cli.require(text == (ROOT / "Tools/ota" / name).read_text(encoding="utf-8"), "nonliteral source change")
    old = ast.parse((AREA / "test_p34_cost_assets.py").read_bytes())
    new = ast.parse((ROOT / "tests/ota/test_p34_cost_assets.py").read_bytes())
    def methods(tree):
        return {n.name: ast.dump(n) for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name != "context_check"}
    cli.require(methods(old) == methods(new), "unrelated test bodies changed")
    cli.require(not OUT.exists(), "preserve test evidence")
    env = host.environment(s, OUT)
    env["P34_TEST_OUT"] = str(OUT)
    host.command(s, OUT, "runner", [sys.executable, "-I", "-S", "-B", "-X", "utf8", __file__, "child"], env, 900)
    result = s.read(OUT / "result.json")
    selection = s.read(OUT / "selection.json")
    cli.require(result["passed"] and result["tests"] == 5 and result["skipped"] == 0, "cost service tests failed")
    reused = sorted(set(selection["all_ids"]) - set(selection["executed_ids"]))
    old_fresh = sorted(set(base["fresh_ids"]) - set(selection["executed_ids"]))
    cli.require(len(old_fresh) == 8 and reused == sorted(base["reused_ids"] + old_fresh), "reuse coverage changed")
    log = Path(base["original_log"]["path"]).read_text(encoding="utf-8")
    cli.require(cli.record(base["original_log"]["path"]) == base["original_log"], "old log changed")
    for name in old_fresh:
        cls, method = name.rsplit(".", 1)
        cli.require(method + " (" + cls + "." + method + ") ... ok" in log or
                    method + " (" + cls + ") ... ok" in log, "missing direct PASS: " + name)
    value = dict(result, tests=356, executed_tests=5, reused_tests=351,
        fresh_ids=selection["executed_ids"], reused_ids=reused, prior_coverage=cli.record(BASE),
        executed=cli.record(OUT / "result.json"), original_log=cli.record(OUT / "unittest.log"),
        direct_eight_log=base["original_log"], reused_343_origin=base["proof"],
        scope="Development only: metadata literals; five real cost tests, 351 unaffected prior PASS cases")
    s.write(OUT / "coverage.json", value)
    s.write(s.base / "tests/latest.json", value, replace=True)
    print("COST_FILENAME_PASS executed5 reused351 coverage356")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    s = cli.Store(ROOT)
    if sys.argv[1:] == ["manifest"]:
        manifest(s)
    elif sys.argv[1:] == ["test"]:
        test(s)
    elif sys.argv[1:] == ["child"]:
        child()
    else:
        raise RuntimeError("expected manifest, test or child")
