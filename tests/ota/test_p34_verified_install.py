"""Exercise the reused install worker without phone or filesystem mutation."""
from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_verified_install as f


class Tests(unittest.TestCase):
    def setup_worker(self, power="mWakefulness=Asleep", installed=True):
        values, commands = {}, []
        store = SimpleNamespace(checked=lambda p: Path(p),
            raw=lambda p, v: values.update({str(p): v}),
            write=lambda p, v: values.update({str(p): v}), read=lambda p: values[str(p)])
        api = f.Installer(store, ROOT / "prior", ROOT / "apk.json", "a" * 40, ROOT / "unused")
        def command(args, **kwargs):
            commands.append(args)
            if args == ["shell", "dumpsys", "power"]: return power
            raise RuntimeError("unexpected command")
        phone = SimpleNamespace(phone_identity=lambda: None, command=command)
        runtime = lambda: (None, dict(usb=lambda *args: nullcontext(),
            installed=lambda *args: {} if installed else None), phone,
            SimpleNamespace(device_lock=nullcontext))
        loader = SimpleNamespace(run_path=lambda p: dict(runtime=runtime))
        inputs = lambda s: ({}, dict(summary=dict(captureId="completed")), dict(sha256="prior"))
        return api, values, commands, inputs, loader

    def test_sleeping_phone_has_no_install_or_stop(self):
        api, values, commands, inputs, loader = self.setup_worker()
        api.worker(input_reader=inputs, runtime_loader=loader)
        result = values[str(api.out / "result.json")]
        self.assertEqual(result["result"], "NEEDS_PHONE_WAKE_NO_INSTALL_ATTEMPTED")
        self.assertTrue(result["usb_closed"] and result["no_uninstall"] and result["no_data_clear"])
        self.assertEqual(commands, [["shell", "dumpsys", "power"]])
        self.assertFalse(any("intent.json" in name for name in values))

    def test_missing_old_apk_fails_before_phone_mutation(self):
        api, values, commands, inputs, loader = self.setup_worker(installed=False)
        with self.assertRaises(RuntimeError): api.worker(input_reader=inputs, runtime_loader=loader)
        self.assertEqual(commands, [])
        self.assertIn("error", values[str(api.out / "result.json")])

    def test_unexpected_awake_state_is_not_a_success(self):
        api, values, commands, inputs, loader = self.setup_worker(power="mWakefulness=Awake")
        with self.assertRaises(RuntimeError): api.worker(input_reader=inputs, runtime_loader=loader)
        self.assertFalse(any(args[0] == "install" for args in commands))
        self.assertIn("error", values[str(api.out / "result.json")])

    def test_arguments_bind_exact_inputs_and_source_commit(self):
        api, _, _, _, _ = self.setup_worker()
        args = api.arguments(ROOT / "tests.json")
        self.assertEqual(args[0], "worker")
        self.assertEqual(args[args.index("--commit") + 1], "a" * 40)
        for commit in ("a" * 39, "A" * 40, "g" * 40):
            with self.assertRaises(RuntimeError):
                f.Installer(api.store, api.trial, api.apk, commit, api.out)
