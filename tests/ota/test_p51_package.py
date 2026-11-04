"""Real archived bytes and synthetic-key packaging, never protected CI admission."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('p51_package', ROOT / 'Tools/ota/p51-package.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
AREA = m.checked(ROOT / '.cache/p51-packaging-impl-20261104-01/tests')


class CandidateInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / 'Tools/ota/p51-candidate-inputs.json').read_bytes())
        cls.data = m.resolve_inputs(cls.manifest)

    def test_exact_original_and_header_only_candidate(self):
        self.assertEqual(m.sha(self.data['base']), self.manifest['packet']['members']['base']['sha256'])
        self.assertEqual(m.sha(self.data['target']), self.manifest['targetSha256'])
        self.assertEqual(self.data['base'][:0x400] + self.data['base'][0x460:],
                         self.data['target'][:0x400] + self.data['target'][0x460:])
        self.assertEqual(len(self.data['boot']), 14800)
        self.assertEqual(self.data['row']['etu_bytes'], 1048576)

    def test_wrong_version_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['targetVersion'] = '3.3.15'
        with self.assertRaisesRegex(ValueError, 'recipe'):
            m.resolve_inputs(bad)

    def test_wrong_archive_bytes_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['packet']['parts'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.resolve_inputs(bad)

    def test_path_escape_rejected(self):
        for path in ('../outside', 'D:/outside', 'D:outside', '/outside', 'a/../b', 'a\\b', '//server/share'):
            with self.assertRaises(ValueError):
                m.read(dict(path=path, bytes=1, sha256='0' * 64))

    def test_wrong_boot_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['boot']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.resolve_inputs(bad)

    def test_wrong_target_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['targetSha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'target identity'):
            m.resolve_inputs(bad)

    def test_wrong_reference_rejected(self):
        bad = copy.deepcopy(self.manifest)
        bad['reference']['stream']['bytes'] -= 1
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.resolve_inputs(bad)

    def test_failed_native_command_preserves_redacted_originals(self):
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='failed-native-', dir=AREA)))
        evidence = m.checked(out / 'evidence/native')
        key = '0123456789AbCdEf0123456789abcdef'
        env = dict(os.environ, P51_TEST_DIAGNOSTIC=key)
        command = [sys.executable, '-I', '-S', '-B', '-c',
            "import os,sys;print('compile stage');print('error: '+os.environ['P51_TEST_DIAGNOSTIC']+' 0x89AbCdEfu',file=sys.stderr);sys.exit(1)"]
        with mock.patch.dict(m.os.environ, {'OTA_AES_KEY': key}):
            with self.assertRaisesRegex(ValueError, 'Native process failed'):
                m.native_command('compile', command, env, evidence)
        stderr = (evidence / 'compile.stderr.txt').read_text()
        self.assertNotIn(key, stderr)
        self.assertNotIn('89ABCDEF', stderr)
        self.assertNotIn('89AbCdEf', stderr)
        self.assertIn('error:', stderr)
        self.assertEqual(json.loads((evidence / 'compile.process.json').read_bytes())['exitCode'], 1)
        self.assertEqual((evidence / 'compile.stdout.txt').read_text(), 'compile stage\n')

    def test_native_timeout_closes_compiler_descendants_before_private_cleanup(self):
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='timeout-native-', dir=AREA)))
        evidence = m.checked(out / 'evidence/native')
        code = "import subprocess,sys,time;p=subprocess.Popen([sys.executable,'-I','-S','-B','-c','import time;time.sleep(30)']);print(p.pid,flush=True);time.sleep(30)"
        with self.assertRaisesRegex(ValueError, 'Native process failed'):
            m.native_command('timeout', [sys.executable, '-I', '-S', '-B', '-c', code], dict(os.environ), evidence, timeout=1)
        receipt = json.loads((evidence / 'timeout.process.json').read_bytes())
        self.assertTrue(receipt['timeout'] and receipt['treeCleanupComplete'])
        self.assertFalse((out / 'private/native-active.json').exists())
        pid = int((evidence / 'timeout.stdout.txt').read_text().strip())
        if os.name == 'nt':
            import ctypes
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.OpenProcess.restype = ctypes.c_void_p
            handle = kernel.OpenProcess(0x100000, False, pid)
            if handle:
                try:
                    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
                    self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0)
                finally:
                    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                    kernel.CloseHandle(handle)
        else:
            proc = Path('/proc') / str(pid) / 'stat'
            self.assertTrue(not proc.exists() or proc.read_text().split(') ')[1].split()[0] == 'Z')

    def test_real_roundtrip_and_native_negatives_with_fixture_key(self):
        self.assertFalse(os.environ.get('OTA_AES_KEY'), 'Do not inject a protected key into host tests')
        AREA.mkdir(parents=True, exist_ok=True)
        out = m.checked(Path(tempfile.mkdtemp(prefix='native-', dir=AREA)))
        private = m.checked(out / 'private')
        private.mkdir()
        key = bytes.fromhex('01' * 16)
        m.save(private / 'key.h', ''.join('#define OTA_AES_KEY_1_WORD%d 0x01010101u\n' % i for i in range(4)).encode())
        m.save(out / 'inputs/base.bin', self.data['base'])
        result = m.package(self.data, key, out / 'prepared')
        self.assertEqual(result['referenceBytes'], 1048576)
        self.assertEqual((out / 'prepared/patch.etu').read_bytes(), (out / 'prepared/reference-1MiB.etu').read_bytes())
        cc = os.environ.get('P51_TEST_CC') or shutil.which('gcc')
        self.assertIsNotNone(cc, 'Native compiler required; do not turn a skipped check into PASS')
        native = m.native_verify(self.data, out / 'prepared', private, cc)
        self.assertEqual(len(native['checks']), 5)
        m.save_json(out / 'SELFTEST-ONLY.json', dict(protectedKey=False, installable=False, publishable=False,
                                                    result=result, native=native))
        with self.assertRaisesRegex(ValueError, 'Preserve'):
            m.package(self.data, key, out / 'prepared')


if __name__ == '__main__':
    unittest.main()
