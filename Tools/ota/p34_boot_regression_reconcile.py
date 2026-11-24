"""Reconcile unchanged original PASS cases with five targeted host retests."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

OUT = ROOT / ".cache/p34-boot/regression-reconcile"
ORIGINAL = ROOT / ".cache/p34-session/tests/1790772626556013400"
TIMEOUT = ROOT / ".cache/p34-session/tests/1790773556342602100/timeout.json"
METHOD = "test_old_matrix_is_unchanged_and_window8_has_separate_axes"


def child():
    root_tests = cli.load_module("p34_reconcile_suite", ROOT / "tests/ota/test_p34_session.py")
    boot = cli.load_module("p34_boot_copy_suite", ROOT / "tests/ota/test_p34_boot_ota.py")
    suite = unittest.TestSuite([root_tests.window8_tests.Window8Tests(METHOD)])
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(boot.Tests))
    ids = [test.id() for test in suite]
    with (OUT / "targeted.log").open("x", encoding="utf-8", buffering=1) as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    cli.Store(ROOT).write(OUT / "targeted.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        ids=ids, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped)))
    return int(not result.wasSuccessful())


def run():
    store = cli.Store(ROOT)
    cli.require(not store.checked(OUT).exists(), "preserve prior reconciliation")
    old = store.read(ORIGINAL / "result.json")
    cli.require((old["tests"], old["failures"], old["errors"], old["skipped"]) == (350, 1, 0, 0),
                "unexpected original test result")
    source = ROOT / "tests/ota/test_p34_window8.py"
    changed = [item for item in old["sources"] if cli.record(item["path"]) != item]
    cli.require(len(changed) == 1 and Path(changed[0]["path"]) == source, "changes exceed one test method")
    raw = source.read_bytes()
    inserted = (b'            wanted = (dict(expected, s04=(921600, 28)) if group == cli.BOOT_COPY_GROUP else\n'
                b'                      dict(expected, s04=(921600, 32))')
    previous = b'            wanted = (dict(expected, s04=(921600, 32))'
    cli.require(raw.count(inserted) == 1, "unexpected matrix test edit")
    restored = raw.replace(inserted, previous)
    cli.require(len(restored) == changed[0]["bytes"] and
                hashlib.sha256(restored).hexdigest() == changed[0]["sha256"], "original test reconstruction differs")
    trees = [ast.parse(blob) for blob in (restored, raw)]
    for tree in trees:
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Window8Tests")
        cli.require(sum(isinstance(node, ast.FunctionDef) and node.name == METHOD for node in cls.body) == 1,
                    "matrix test is not unique")
        cls.body = [node for node in cls.body if not (isinstance(node, ast.FunctionDef) and node.name == METHOD)]
    cli.require(ast.dump(trees[0]) == ast.dump(trees[1]), "other test definitions changed")
    text = (ORIGINAL / "unittest.log").read_text(encoding="utf-8")
    cases = re.findall(r"^\S+ \(([^)]+)\) \.\.\. (ok|FAIL)$", text, re.M)
    cli.require(len(cases) == len(dict(cases)) == 350 and
                [name for name, state in cases if state != "ok"] == ["p34_window8_tests.Window8Tests." + METHOD],
                "original log does not enumerate the expected sole failure")
    sources = [cli.record(item["path"]) for item in old["sources"]]
    for leaf in ("targeted.log", "targeted.json", "console.log", "result.json", "proof.json"):
        store.checked(OUT / leaf)
    env = dict(os.environ, P34_TEST_OUT=str(OUT))
    for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        path = store.checked(OUT / "host" / key.lower())
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    store.write(OUT / "proof.json", dict(original=cli.record(ORIGINAL / "result.json"),
        original_log=cli.record(ORIGINAL / "unittest.log"), timeout=cli.record(TIMEOUT),
        source_before=changed[0], source_after=cli.record(source),
        reconstructed_original_hash_verified=True, other_ast_unchanged=True, sources=sources))
    command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(Path(__file__)), "child"]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=240,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    store.raw(OUT / "console.log", result.stdout + result.stderr)
    targeted = store.read(OUT / "targeted.json")
    cli.require(result.returncode == 0 and targeted["passed"] and targeted["tests"] == 5 and
                targeted["skipped"] == 0, "targeted checks failed")
    fresh = set(targeted["ids"])
    reused = [name for name, state in cases if state == "ok" and name not in fresh]
    cli.require(len(fresh) == 5 and len(reused) == 345 and fresh | set(reused) == set(dict(cases)),
                "test coverage incomplete or duplicated")
    cli.require(all(cli.record(item["path"]) == item for item in sources), "source changed during targeted checks")
    value = dict(passed=True, tests=350, failures=0, errors=0, skipped=0, device_operations=0,
        sources=sources, executed_tests=5, reused_tests=345, fresh_ids=sorted(fresh), reused_ids=reused,
        scope="development host checks, not a fresh 350-test execution or independent acceptance",
        proof=cli.record(OUT / "proof.json"), targeted=cli.record(OUT / "targeted.json"),
        targeted_log=cli.record(OUT / "targeted.log"), console=cli.record(OUT / "console.log"))
    store.write(OUT / "result.json", value)
    store.write(store.base / "tests/latest.json", value, replace=True)
    print("PASS: 5 executed + 345 unchanged original PASS cases; coverage 350")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    if sys.argv[1:] == ["child"]:
        raise SystemExit(child())
    cli.require(not sys.argv[1:], "unexpected arguments")
    run()
