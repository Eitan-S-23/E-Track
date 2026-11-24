"""Bounded integration regression with explicit unchanged-test reuse."""
import ast
import copy
import os
from pathlib import Path
import runpy
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli
import p34_install_cost as host

AREA = ROOT / ".cache/p34-erase"
BEFORE = AREA / "integration-before"
OUT = AREA / "session-tests-r2"


def stripped(tree, methods, assignments=()):
    tree = copy.deepcopy(tree)
    for node in ast.walk(tree):
        if hasattr(node, "body") and isinstance(node.body, list):
            node.body = [n for n in node.body if not (
                isinstance(n, ast.FunctionDef) and n.name in methods or
                isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in assignments for t in n.targets))]
    return ast.dump(tree)


def child():
    original = unittest.TextTestRunner.run
    base = cli.Store(ROOT).read(BEFORE / "latest.json")
    def flatten(suite):
        for t in suite:
            if isinstance(t, unittest.TestSuite):
                yield from flatten(t)
            else:
                yield t
    def run(runner, suite):
        tests = list(flatten(suite))
        picked = [t for t in tests if t.id() in base["fresh_ids"] or t.id().startswith((
            "__main__.SessionTests.", "p34_erase_suite.", "p34_cost_suite.", "p34_boot_copy_suite.",
            "p34_window8_tests.", "p34_historical_suite."))]
        cli.require(len(tests) == 369, "unexpected suite coverage")
        cli.Store(ROOT).write(OUT / "selection.json", dict(all_ids=[t.id() for t in tests], executed_ids=[t.id() for t in picked]))
        return original(runner, unittest.TestSuite(picked))
    unittest.TextTestRunner.run = run
    runpy.run_path(str(ROOT / "tests/ota/test_p34_session.py"), run_name="__main__")


def run():
    s = cli.Store(ROOT)
    cli.require(not s.checked(OUT).exists(), "preserve integration attempt")
    base = s.read(BEFORE / "latest.json")
    for item in s.read(BEFORE / "result.json")["files"]:
        cli.require(cli.record(item["path"]) == item, "snapshot changed")
    changed = {Path(i["path"]).name for i in base["sources"] if cli.record(i["path"]) != i}
    cli.require(changed == {"p34_session.py", "p34_session_backend.py", "test_p34_session.py",
                           "p34_patch_assets.py", "p34_patch_preparation.py", "p34_cost_assets.py",
                           "HAL_OTA_Package.cpp", "test_qspi_install_restore.py"}, "unexpected source change")
    for file, methods, assignments in (
        ("p34_session.py", {"patch_asset_groups", "patch_assets_api", "prepare_patch"}, {"ERASE_GROUPS", "NEW_BOOT_GROUPS", "ACK_GAP_GROUPS"}),
        ("p34_session_backend.py", {"__init__", "context", "phone"}, set())):
        a = ast.parse((BEFORE / file).read_bytes())
        b = ast.parse((ROOT / "Tools/ota" / file).read_bytes())
        cli.require(stripped(a, methods, assignments) == stripped(b, methods, assignments), "unexpected integration: " + file)
    a = ast.parse((BEFORE / "test_p34_session.py").read_bytes())
    b = ast.parse((ROOT / "tests/ota/test_p34_session.py").read_bytes())
    cli.require(ast.dump(ast.Module(body=a.body[:-1], type_ignores=[])) ==
                ast.dump(ast.Module(body=b.body[:-1], type_ignores=[])), "existing test bodies changed")
    old = runpy.run_path(str(BEFORE / "p34_session.py"))
    for name in ("FULL_VERSIONS", "PREDECESSOR_GROUPS", "ALL_PATCH_GROUPS"):
        cli.require(all(getattr(cli, name)[k] == v for k, v in old[name].items()), "old group changed")
    for group in old["GROUPS"]:
        cli.require(old["cells_for"](group) == cli.cells_for(group), "old axes changed")
        if group in old["ALL_PATCH_GROUPS"]:
            cli.require(old["patch_asset_groups"](group) == cli.patch_asset_groups(group), "old dependencies changed")
    old_sources = AREA / "provenance-before"
    for file, methods in (("p34_patch_assets.py", {"decoder_equivalence"}),
                          ("p34_patch_preparation.py", {"verify_records"}),
                          ("p34_cost_assets.py", {"load"}), ("p34_erase_assets.py", {"load"})):
        a = ast.parse((old_sources / file).read_bytes())
        text = (ROOT / "Tools/ota" / file).read_text().replace("import p34_historical_inputs as historical\n", "")
        b = ast.parse(text)
        cli.require(stripped(a, methods) == stripped(b, methods), "non-provenance change: " + file)
    review = s.read(AREA / "build-review/result.json")
    tests = s.read(review["tests"]["path"])
    cli.require(tests["result"] == "ERASE_HOST_PASS", "changed HAL lacks executed checks")
    for item in tests["inputs"] + [tests["hal"], review["tests"]]:
        cli.require(cli.record(item["path"]) == item, "HAL proof changed")
    archive_path = ROOT / "Tools/ota/p34_cost_archive.py"
    marker = "    c = api.installed_context(out)"
    a = (BEFORE / archive_path.name).read_text().split(marker)[1].split('\n\nif __name__')[0]
    b = archive_path.read_text().split(marker)[1].split('\n\nif __name__')[0]
    cli.require(a == b, "archive operational guards changed")
    archive = cli.load_module("erase_archive_test", archive_path)
    for current in ("wrong", "20260930T175922-37800"):
        with mock.patch.object(cli, "Store", return_value=s), mock.patch.object(s, "current", return_value=current), \
                mock.patch.object(cli, "verify_tests", return_value={}), \
                mock.patch.object(cli, "backend", side_effect=RuntimeError("bound backend")) as backend:
            try:
                archive.run(erase=True)
            except RuntimeError as e:
                cli.require(("owner changed" if current == "wrong" else "bound backend") in str(e), "wrong archive gate")
            else:
                raise RuntimeError("archive test escaped gate")
            if current != "wrong":
                cli.require(backend.call_args.args[1:] == (s.base / "profile-cost-measure.json", "cost-measure"), "wrong archive binding")
            else:
                backend.assert_not_called()
    cli.require(not (AREA / "archive-30239").exists(), "archive check mutated device/output")
    env = host.environment(s, OUT)
    env["P34_TEST_OUT"] = str(OUT)
    s.write(OUT / "scope.json", dict(before=cli.record(BEFORE / "result.json"), prior=cli.record(BEFORE / "latest.json"),
        unchanged_old_test_AST=True, unchanged_old_groups_axes_dependencies=True, unchanged_nonintegration_AST=True,
        changed_hal_executed=review["tests"], archive_guards_unchanged=True, archive_binding_checks=2,
        archive_source=cli.record(archive_path)))
    host.command(s, OUT, "runner", [sys.executable, "-I", "-S", "-B", "-X", "utf8", __file__, "child"], env, 900)
    result, selection = s.read(OUT / "result.json"), s.read(OUT / "selection.json")
    cli.require(result["passed"] and not result["skipped"] and result["tests"] == len(selection["executed_ids"]), "integration failed")
    old_ids = set(base["fresh_ids"] + base["reused_ids"])
    new_ids = set(selection["all_ids"]) - old_ids
    cli.require(len(new_ids) == 12 and all(i.startswith(("p34_erase_suite.", "p34_historical_suite.")) for i in new_ids), "unaccounted test change")
    reused = sorted(set(selection["all_ids"]) - set(selection["executed_ids"]))
    cli.require(set(reused) <= old_ids, "missing original PASS")
    value = dict(result, tests=369, executed_tests=result["tests"], reused_tests=len(reused),
        fresh_ids=selection["executed_ids"], reused_ids=reused, prior_coverage=cli.record(BEFORE / "latest.json"),
        executed=cli.record(OUT / "result.json"), original_log=cli.record(OUT / "unittest.log"),
        proof=cli.record(OUT / "scope.json"), scope="Development only; bounded erase integration checks and unchanged original case reuse")
    s.write(OUT / "coverage.json", value)
    s.write(s.base / "tests/latest.json", value, replace=True)
    print("ERASE_SESSION_PASS", result["tests"], "executed", len(reused), "reused")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    if sys.argv[1:] == ["child"]:
        child()
    else:
        cli.require(not sys.argv[1:], "unexpected arguments")
        run()
