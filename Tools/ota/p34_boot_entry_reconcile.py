"""Targeted validation of the Boot-only predecessor entry repair."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

OUT = ROOT / ".cache/p34-boot/entry-fix"
BASE = ROOT / ".cache/p34-boot/regression-reconcile/result.json"
WINDOW_TESTS = ("test_old_matrix_is_unchanged_and_window8_has_separate_axes",
                "test_U_advances_once_to_window8_and_attempted_V_is_never_replayed",
                "test_window8_cannot_use_prefix_axes_or_a_different_U_owner")


def child():
    module = cli.load_module("p34_entry_suite", ROOT / "tests/ota/test_p34_session.py")
    boot = cli.load_module("p34_boot_copy_suite", ROOT / "tests/ota/test_p34_boot_ota.py")
    suite = unittest.TestSuite(module.window8_tests.Window8Tests(name) for name in WINDOW_TESTS)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(boot.Tests))
    ids = [test.id() for test in suite]
    with (OUT / "targeted.log").open("x", encoding="utf-8", buffering=1) as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    cli.Store(ROOT).write(OUT / "targeted.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        ids=ids, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped)))
    return int(not result.wasSuccessful())


def run():
    store = cli.Store(ROOT)
    cli.require(not store.checked(OUT).exists(), "preserve prior repair evidence")
    base = store.read(BASE)
    cli.require(base["passed"] and base["tests"] == 350, "prior reconciled evidence missing")
    for key in ("proof", "targeted", "targeted_log", "console"):
        cli.require(cli.record(base[key]["path"]) == base[key], "prior proof changed")
    proof = store.read(base["proof"]["path"])
    for key in ("original", "original_log", "timeout"):
        cli.require(cli.record(proof[key]["path"]) == proof[key], "original proof changed")
    backend = ROOT / "Tools/ota/p34_session_backend.py"
    test = ROOT / "tests/ota/test_p34_boot_ota.py"
    changed = [item for item in base["sources"] if cli.record(item["path"]) != item]
    cli.require({Path(item["path"]) for item in changed} == {backend, test}, "unexpected source changes")
    raw = backend.read_bytes()
    previous = b'            cli.require(value["plan"]["target_bindings"] == c.bindings, "window-8 receiver differs from verified predecessor")\n'
    replacement = (b'            if group == cli.BOOT_COPY_GROUP:\n'
                   b'                self.patch_api.verify_transition(value["plan"]["target_bindings"], c.bindings)\n'
                   b'            else:\n' + b'    ' + previous)
    cli.require(raw.count(replacement) == 1, "unexpected predecessor repair")
    restored_backend = raw.replace(replacement, previous)
    raw_test = test.read_bytes()
    first = raw_test.index(b"    def test_predecessor_admits_only_verified_boot_transition(self):")
    end = raw_test.index(b"    def test_assets_and_exact_boot_transition(self):", first)
    restored_test = (raw_test[:first] + raw_test[end:]).replace(b"from unittest import mock\n", b"")
    for item in changed:
        blob = restored_backend if Path(item["path"]) == backend else restored_test
        cli.require(len(blob) == item["bytes"] and hashlib.sha256(blob).hexdigest() == item["sha256"],
                    "exact prior source reconstruction failed")
    sources = [cli.record(item["path"]) for item in base["sources"]]
    for leaf in ("targeted.log", "targeted.json", "console.log", "proof.json", "result.json"):
        store.checked(OUT / leaf)
    env = dict(os.environ, P34_TEST_OUT=str(OUT))
    for key in ("TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        path = store.checked(OUT / "host" / key.lower())
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    store.write(OUT / "proof.json", dict(base=cli.record(BASE), old_sources=changed, sources=sources,
        exact_prior_reconstruction=True,
        change_scope="Only BOOT_COPY_GROUP takes verified transition; original equality else branch preserved. "
                     "One new negative/positive predecessor test; all other source bytes unchanged."))
    command = [sys.executable, "-I", "-S", "-B", "-X", "utf8", str(Path(__file__)), "child"]
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=240,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    store.raw(OUT / "console.log", result.stdout + result.stderr)
    fresh_result = store.read(OUT / "targeted.json")
    cli.require(result.returncode == 0 and fresh_result["passed"] and fresh_result["tests"] == 8 and
                fresh_result["skipped"] == 0, "targeted entry checks failed")
    old_ids = set(base["fresh_ids"] + base["reused_ids"])
    fresh = set(fresh_result["ids"])
    added = "p34_boot_copy_suite.Tests.test_predecessor_admits_only_verified_boot_transition"
    cli.require(fresh - old_ids == {added} and len(fresh) == 8, "unexpected test coverage")
    reused = sorted(old_ids - fresh)
    cli.require(len(reused) == 343 and set(reused).issubset(base["reused_ids"]),
                "reused tests must be direct unchanged original PASS cases")
    cli.require(all(cli.record(item["path"]) == item for item in sources), "source changed during tests")
    value = dict(passed=True, tests=351, failures=0, errors=0, skipped=0, device_operations=0,
        sources=sources, executed_tests=8, reused_tests=343, fresh_ids=sorted(fresh), reused_ids=reused,
        scope="development host coverage; not fresh351 execution or independent acceptance",
        proof=cli.record(OUT / "proof.json"), targeted=cli.record(OUT / "targeted.json"),
        targeted_log=cli.record(OUT / "targeted.log"), console=cli.record(OUT / "console.log"))
    store.write(OUT / "result.json", value)
    store.write(store.base / "tests/latest.json", value, replace=True)
    print("PASS: 8 executed + 343 original PASS reused; coverage351")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    if sys.argv[1:] == ["child"]:
        raise SystemExit(child())
    cli.require(not sys.argv[1:], "unexpected arguments")
    run()
