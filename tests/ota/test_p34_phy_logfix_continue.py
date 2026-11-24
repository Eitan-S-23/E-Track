"""Closed-inventory guards before stopping an unrecorded process; no device IO."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_phy_logfix_continue as f


class Guards(unittest.TestCase):
    def test_exact_full_old_store_and_changed_state(self):
        observed = json.loads((f.inspect.OUT / "result.json").read_bytes())
        config = (f.inspect.OUT / "runtime-config.json").read_bytes()
        headers = [dict(kind="open", pid=25415)]
        f.blocked_inventory(observed["names"], config, config, headers, observed["pid"])
        for names, raw, rows in [(observed["names"][:-1], config, headers),
                (observed["names"], config + b" ", headers),
                (observed["names"], config, [dict(kind="open", pid=int(observed["pid"]))]),
                (observed["names"], config, [])]:
            with self.assertRaises(RuntimeError): f.blocked_inventory(names, raw, config, rows, observed["pid"])

    def test_previous_originals_still_validate(self):
        f.trial.tests(f.cli.Store(ROOT))
        f.trial.installed(f.cli.Store(ROOT))
        self.assertNotEqual(f.RECOVERY, f.base.RECOVERY)


if __name__ == "__main__":
    f.cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                  "isolated explicit root required")
    s = f.cli.Store(ROOT)
    s.checked(f.HOST)
    f.cli.require(not f.HOST.exists(), "preserve test evidence")
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Guards))
    log = s.raw(f.HOST / "tests.log", stream.getvalue().encode())
    s.write(f.HOST / "result.json", dict(passed=result.wasSuccessful(), count=result.testsRun,
        sources=f.sources(), log=log, hardware=False))
    print(stream.getvalue())
    sys.exit(not result.wasSuccessful())
