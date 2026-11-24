"""Regressions for reset exceptions across independently loaded host modules."""
import io
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
helper = runpy.run_path(str(Path(__file__).with_name("baud_resume_clock.py")), run_name="tested_reset_resume")
r = helper["runtime"]()
OUT = r.b.checked(r.b.OUT / "host-tests-clock-resume-001")


class ResetLink:
    def __init__(self, exception):
        self.exception, self.ram_writes, self.rtt_address = exception, [], None

    def running(self):
        raise self.exception("planned reset")

    def read(self, *_):
        raise AssertionError("must not read old App RAM during reset")


class ResetTests(unittest.TestCase):
    def test_tuning_and_capture_use_the_same_transition_type(self):
        tune = r.load("canonical_type_test", ROOT / "Tools/ota/baud_tune.py")
        self.assertIs(tune.ControlLink.running.__globals__["Transition"], r.m.passive.Transition)
        self.assertIs(tune.ControlLink.running, r.m.BoundLink.running)

    def test_canonical_reset_is_pending_without_old_ram_access(self):
        reader = r.m.ImageReader(ResetLink(r.m.passive.Transition), {})
        self.assertIsNone(reader.poll())
        self.assertIsNone(reader.channel)

    def test_foreign_transition_reproduces_the_original_failure(self):
        class ForeignTransition(RuntimeError):
            pass
        reader = r.m.ImageReader(ResetLink(ForeignTransition), {})
        with self.assertRaises(ForeignTransition):
            reader.poll()


if __name__ == "__main__":
    r.b.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "isolated explicit root required")
    r.b.require(not OUT.exists(), "preserve test evidence")
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    r.save(OUT / "result.json", dict(passed=result.wasSuccessful(), tests=result.testsRun,
        output=output.getvalue(), source=r.b.record(Path(__file__).with_name("baud_resume_clock.py")),
        parent=r.b.record(helper["PARENT"]), test_source=r.b.record(Path(__file__)), runtime_sources=r.sources(), hardware=False))
    print(output.getvalue(), flush=True)
    raise SystemExit(0 if result.wasSuccessful() else 1)
