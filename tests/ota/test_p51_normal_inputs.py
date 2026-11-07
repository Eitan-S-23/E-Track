"""Real archived source admission and contained normal-command regression."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('normal_inputs', ROOT / 'Tools/ota/p51-normal-inputs.py')
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
m = n.m
AREA = m.checked(Path(os.environ.get('P51_TEST_AREA', ROOT / '.cache/p51-normal-tests')))
CONFIG = json.loads((ROOT / 'Tools/ota/p51-normal-inputs.json').read_bytes())


class NormalInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        AREA.mkdir(parents=True, exist_ok=True)
        cls.out = m.checked(Path(tempfile.mkdtemp(prefix='originals-', dir=AREA)))
        cls.proof = n.materialize(CONFIG, cls.out)

    def test_real_originals_have_real_delta_and_no_reference_search(self):
        with mock.patch.object(m.encoding, 'encode', side_effect=AssertionError('not a reference route')):
            n.check_materialized(CONFIG, self.out)
        self.assertTrue(self.proof['sourceChangesOutsideFwHeader'])
        self.assertEqual(self.proof['roles']['base']['originalBuild']['versionCode'], 30313)
        self.assertEqual(self.proof['roles']['target']['originalBuild']['versionCode'], 30319)
        self.assertEqual(self.proof['roles']['base']['originalBuild']['keyBinding'],
                         self.proof['roles']['target']['originalBuild']['keyBinding'])
        self.assertEqual(self.proof['sourceCompilations'], 0)
        self.assertEqual(self.proof['bootInstallation'], 'FORBIDDEN')

    def test_every_materialized_original_is_rechecked_from_the_archives(self):
        for role in ('base', 'target'):
            for record in self.proof['roles'][role]['files'].values():
                path = self.out / 'inputs' / record['path']
                raw = path.read_bytes()
                with self.subTest(role=role, path=record['path']):
                    path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
                    try:
                        with self.assertRaisesRegex(ValueError, 'original byte drift'):
                            n.check_materialized(CONFIG, self.out)
                    finally:
                        path.write_bytes(raw)

    def test_changed_proof_or_config_is_not_a_valid_source(self):
        for name in ('manifest.json', 'normal-source-proof.json'):
            path = self.out / 'inputs' / name
            original = path.read_bytes()
            path.write_bytes(b'{}')
            try:
                with self.assertRaisesRegex(ValueError, 'source proof drift'):
                    n.check_materialized(CONFIG, self.out)
            finally:
                path.write_bytes(original)

    def test_existing_admission_outputs_are_never_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'Preserve prior'):
            n.materialize(CONFIG, self.out)

    def test_original_manifest_hash_is_not_a_boolean_claim(self):
        for role in ('baseSource', 'targetSource'):
            changed = copy.deepcopy(CONFIG)
            changed[role]['sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'byte identity'):
                n.resolve(changed)

    def test_versions_modes_and_purposes_fail_closed(self):
        for key, value in [('baseVersion', '3.3.19'), ('targetVersion', '3.3.20'),
                           ('mode', 'new-source'), ('purpose', 'fixed-load-benchmark'),
                           ('productionPublishable', True), ('basePurpose', 'formal-release')]:
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    n.validate_config(dict(CONFIG, **{key: value}))

    def test_misbound_source_commit_fails_before_materialization(self):
        for key in ('baseSourceCommit', 'targetSourceCommit'):
            out = m.checked(Path(tempfile.mkdtemp(prefix='misbound-', dir=AREA)))
            with self.assertRaisesRegex(ValueError, 'lineage mismatch'):
                n.materialize(dict(CONFIG, **{key: '0' * 40}), out)
            self.assertFalse((out / 'inputs').exists())

    def test_native_request_rejects_other_tools_and_uncontained_cwd(self):
        out = m.checked(Path(tempfile.mkdtemp(prefix='command-', dir=AREA)))
        path = out / 'private/request.json'
        request = dict(label='normal-step-1', timeout=330, cwd=str(out / 'normal/base/work'),
            argv=[sys.executable, '-B', str(ROOT / 'Tools/etu_pack.py'), 'finalize'])
        for change in [dict(argv=['cmd.exe', '/c', 'echo', 'wrong']), dict(timeout=600),
                       dict(cwd=str(ROOT.parent)), dict(label='compiler-1')]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(dict(request, **change)), encoding='utf-8')
            with mock.patch.object(m, 'native_command', side_effect=AssertionError('must reject before spawn')):
                with self.assertRaises(ValueError):
                    n.command(out, path)


if __name__ == '__main__':
    unittest.main()
