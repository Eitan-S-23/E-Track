"""Exercise the actual bounded, one-shot module-startup reset policy."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
CASES = ('ready_preserves_new_link', 'fragmented', 'wrap', 'silent', 'timeout_once',
         'no_ok', 'bad_ready', 'late', 'noise', 'stale_ready', 'tx_blocked',
         'tx_partial', 'line_recovery', 'ready_once')
NAME_CASES = ('unchanged', 'unchanged_compact', 'legacy_hyphen', 'fragmented', 'wrap',
              'silent', 'query_silent', 'rejected', 'echo_is_not_ack', 'bad_ack', 'noise',
              'stale_name', 'tx_blocked', 'tx_partial', 'line_recovery', 'bad_query', 'rename_once')


class StartupResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('startup_io',
            ROOT / '.agents/skills/e-track-flutter-debug/scripts/host_io.py')
        io = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(io)
        cache = io.checked_output(ROOT, ROOT / '.cache/bt-startup-reset-tests')
        cache.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix='run-', dir=cache))
        cls.executable = io.checked_output(ROOT, directory / 'startup-reset.exe')
        cls.env = dict(os.environ, TEMP=str(directory), TMP=str(directory), TMPDIR=str(directory))
        compiler = shutil.which('g++')
        if compiler is None:
            raise RuntimeError('Host g++ required')
        cls.name_executable = io.checked_output(ROOT, directory / 'startup-name.exe')
        for source, output in (('bt_startup_reset_test.cpp', cls.executable),
                               ('bt_startup_name_test.cpp', cls.name_executable)):
            command = [compiler, '-std=c++11', '-Wall', '-Wextra', '-Werror',
                '-static-libgcc', '-static-libstdc++', '-I', str(ROOT / 'Libraries'),
                str(ROOT / 'tests/ota' / source), '-o', str(output)]
            build = subprocess.run(command, cwd=ROOT, env=cls.env, capture_output=True, text=True, timeout=60)
            if build.returncode:
                raise RuntimeError(build.stdout + build.stderr)
        print('Startup policy SHA-256: ' + hashlib.sha256(
            (ROOT / 'Libraries/Bluetooth/StartupReset.h').read_bytes()).hexdigest())
        print('Retained fixture: ' + str(cls.executable))
        print('Startup name SHA-256: ' + hashlib.sha256(
            (ROOT / 'Libraries/Bluetooth/StartupName.h').read_bytes()).hexdigest())

    def test_only_startup_uses_reset_before_attaching_ota(self):
        source = (ROOT / 'USER/HAL/HAL_Bluetooth.cpp').read_text(encoding='utf-8')
        init = source.split('void HAL::BT_Init()', 1)[1].split('void HAL::BT_SleepMode()', 1)[0]
        self.assertEqual(source.count('s_bt_startup_reset.Run('), 1)
        self.assertLess(init.index('BT_SERIAL.begin('), init.index('s_bt_startup_reset.Run('))
        self.assertLess(init.index('s_bt_startup_reset.Run('), init.index('BT_SERIAL.attachInterrupt('))
        self.assertIn('#if !CONFIG_BT_BAUD_EXPERIMENT\n    BtStartupPort', init)
        self.assertNotIn('flush(', init)
        port = source.split('struct BtStartupPort', 1)[1].split('void HAL::BT_Init()', 1)[0]
        self.assertIn('return BT_SERIAL.write((const uint8_t*)bytes, count);', port)

    def test_fixed_candidate_names_before_the_only_reset_without_tuning_other_settings(self):
        source = (ROOT / 'USER/HAL/HAL_Bluetooth.cpp').read_text(encoding='utf-8')
        init = source.split('void HAL::BT_Init()', 1)[1].split('void HAL::BT_SleepMode()', 1)[0]
        self.assertEqual(init.count('BT_SetName();'), 1)
        self.assertLess(init.index('BT_SERIAL.begin('), init.index('BT_SetName();'))
        self.assertLess(init.index('BT_SetName();'), init.index('s_bt_startup_reset.Run('))
        naming = source.split('void HAL::BT_SetName()', 1)[1].split('void HAL::BT_printf', 1)[0]
        self.assertIn('#if CONFIG_BT_BAUD_EXPERIMENT\n', naming)
        self.assertNotIn('P34_OTA_FIXED_CONFIG', naming)
        self.assertEqual(source.count('s_bt_startup_name.Run('), 1)
        policy = (ROOT / 'Libraries/Bluetooth/StartupName.h').read_text(encoding='utf-8')
        for command in ('AT+MAC', 'AT+UART', 'AT+UUID', 'AT+RESET', 'AT+REBOOT'):
            self.assertNotIn(command, policy)


def test_case(name, naming=False):
    def run(self):
        result = subprocess.run([str(self.name_executable if naming else self.executable), name], cwd=ROOT, env=self.env,
            capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())
    return run


for case in CASES:
    setattr(StartupResetTests, 'test_' + case, test_case(case))
for case in NAME_CASES:
    setattr(StartupResetTests, 'test_name_' + case, test_case(case, naming=True))

if __name__ == '__main__':
    unittest.main(verbosity=2)
