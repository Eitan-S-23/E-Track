"""Run changed cost/Boot/start checks and retain direct original PASS anchors."""
import ast
import copy
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host

OUT = ROOT / ".cache/p34-cost/session-tests"
BASE = ROOT / ".cache/p34-boot/identity-fix/result.json"
BEFORE = ROOT / ".cache/p34-cost/session-before"


def child():
    s = cli.Store(ROOT)
    selected_old = set(s.read(BASE)["fresh_ids"])
    original_run = unittest.TextTestRunner.run
    def flatten(suite):
        for test in suite:
            if isinstance(test, unittest.TestSuite):
                yield from flatten(test)
            else:
                yield test
    def selected_run(runner, suite):
        tests = list(flatten(suite))
        picked = [t for t in tests if t.id() in selected_old or t.id().startswith("p34_cost_suite.Tests.")]
        cli.require(len(tests) == 356 and len(picked) == 13, "unexpected current suite coverage")
        s.write(OUT / "selection.json", dict(all_ids=[t.id() for t in tests], executed_ids=[t.id() for t in picked]))
        return original_run(runner, unittest.TestSuite(picked))
    unittest.TextTestRunner.run = selected_run
    runpy.run_path(str(ROOT / "tests/ota/test_p34_session.py"), run_name="__main__")


def without_functions(tree, names):
    tree = copy.deepcopy(tree)
    for node in ast.walk(tree):
        if hasattr(node, "body") and isinstance(node.body, list):
            node.body = [x for x in node.body if not isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef)) or x.name not in names]
    return tree


def prove_scope(s):
    snapshots = s.read(BEFORE / "result.json")
    for item in snapshots["files"]:
        cli.require(cli.record(item["path"]) == item, "pre-edit snapshot changed")
    base = s.read(BASE)
    changed = {Path(x["path"]).name for x in base["sources"] if cli.record(x["path"]) != x}
    cli.require(changed == {"p34_session.py", "p34_session_backend.py", "test_p34_window8.py", "test_p34_session.py"},
                "change scope exceeds declared integration")
    old = runpy.run_path(str(BEFORE / "p34_session.py"))
    for name in ("FULL_VERSIONS", "PREDECESSOR_GROUPS", "ALL_PATCH_GROUPS"):
        cli.require(all(getattr(cli, name)[k] == v for k, v in old[name].items()), "historical group changed")
    for group in old["GROUPS"]:
        cli.require(old["cells_for"](group) == cli.cells_for(group), "historical axes changed")
        if group in old["ALL_PATCH_GROUPS"]:
            cli.require(old["patch_asset_groups"](group) == cli.patch_asset_groups(group), "historical asset dependencies changed")
    a = ast.parse((BEFORE / "p34_session.py").read_bytes())
    b = ast.parse((ROOT / "Tools/ota/p34_session.py").read_bytes())
    for tree in (a, b):
        tree.body = [n for n in tree.body if not isinstance(n, ast.Assign) or not any(
            isinstance(t, ast.Name) and t.id in ("COST_GROUPS", "NEW_BOOT_GROUPS", "ACK_GAP_GROUPS") for t in n.targets)]
    allowed = {"cells_for", "patch_asset_groups", "patch_assets_api", "prepare_patch"}
    cli.require(ast.dump(without_functions(a, allowed)) == ast.dump(without_functions(b, allowed)), "unexpected CLI change")
    for file, relative, methods in (
        ("p34_session_backend.py", "Tools/ota/p34_session_backend.py", {"__init__", "context", "phone"}),
        ("test_p34_window8.py", "tests/ota/test_p34_window8.py", {"test_old_matrix_is_unchanged_and_window8_has_separate_axes"})):
        a = ast.parse((BEFORE / file).read_bytes())
        b = ast.parse((ROOT / relative).read_bytes())
        cli.require(ast.dump(without_functions(a, methods)) == ast.dump(without_functions(b, methods)), "unexpected change: " + file)
    a = ast.parse((BEFORE / "test_p34_session.py").read_bytes())
    b = ast.parse((ROOT / "tests/ota/test_p34_session.py").read_bytes())
    a.body, b.body = a.body[:-1], b.body[:-1]
    cli.require(ast.dump(a) == ast.dump(b), "existing session test bodies changed")
    return base


def run():
    s = cli.Store(ROOT)
    cli.require(not s.checked(OUT).exists(), "preserve session checks")
    base = prove_scope(s)
    env = host.environment(s, OUT)
    env["P34_TEST_OUT"] = str(OUT)
    for leaf in ("selection.json", "unittest.log", "result.json", "coverage.json", "proof.json"):
        s.checked(OUT / leaf)
    s.write(OUT / "proof.json", dict(base=cli.record(BASE), snapshots=cli.record(BEFORE / "result.json"),
        old_groups_axes_and_dependencies_unchanged=True, unaffected_AST_equal=True,
        modified_scope="New cost groups/loader/profile; same old Boot membership, new cost-only branches and source pins. "
                       "Retest old Boot and start guards plus both real new contexts; no old test body is weakened."))
    host.command(s, OUT, "runner", [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(Path(__file__)), "child"], env, 900)
    executed = s.read(OUT / "result.json")
    selection = s.read(OUT / "selection.json")
    cli.require(executed["passed"] and executed["tests"] == 13 and executed["skipped"] == 0, "affected tests failed")
    reused = sorted(set(selection["all_ids"]) - set(selection["executed_ids"]))
    cli.require(reused == sorted(base["reused_ids"]) and len(reused) == 343, "unaccounted test reuse")
    cli.require(all(cli.record(i["path"]) == i for i in executed["sources"]), "tested sources changed")
    value = dict(executed, tests=356, executed_tests=13, reused_tests=343, fresh_ids=selection["executed_ids"],
        reused_ids=reused, proof=cli.record(OUT / "proof.json"), executed=cli.record(OUT / "result.json"),
        original_log=cli.record(OUT / "unittest.log"), scope="development coverage only;13 executed plus343 direct original PASS")
    s.write(OUT / "coverage.json", value)
    s.write(s.base / "tests/latest.json", value, replace=True)
    print("COST_SESSION_PASS executed13 reused343 coverage356")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    if sys.argv[1:] == ["child"]:
        child()
    else:
        cli.require(not sys.argv[1:], "unexpected arguments")
        run()
