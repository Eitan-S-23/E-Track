"""Real protected archive admission; no key, compiler, network or package generation."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('normal_staging_test', ROOT / 'Tools/ota/p51-normal-staging-inputs.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
CONFIG = json.loads((ROOT / 'Tools/ota/p51-normal-staging-inputs.json').read_bytes())
AREA = s.m.checked(Path(os.environ.get('P51_TEST_AREA', ROOT / '.cache/p51-staging/selftests')))


class NormalStagingInputs(unittest.TestCase):
    def folder(self):
        AREA.mkdir(parents=True, exist_ok=True)
        return s.m.checked(Path(tempfile.mkdtemp(prefix='normal-staging-', dir=AREA)))

    def test_actual_protected_archive_has_no_transform_or_process(self):
        with mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('no process')), \
             mock.patch.dict(os.environ, {}, clear=True):
            data = s.resolve(CONFIG)
        self.assertEqual([s.m.sha(b) for b in data['blobs']], [a['sha256'] for a in CONFIG['assets']])
        self.assertEqual(len(data['blobs'][1]), 12439)
        self.assertEqual(data['proof']['originalOwner']['runId'], '42362540910')
        self.assertEqual(data['proof']['targetSourceCommit'], '1430c8ff7f3bcd9a35bfe158ba697b99021f75f2')
        self.assertEqual(data['proof']['packageGenerations'], 0)

    def test_real_functional_admission_and_only_three_selected_assets(self):
        out = self.folder() / 'admitted'
        with mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('no process')), \
             mock.patch.dict(os.environ, {}, clear=True):
            s.materialize(CONFIG, out)
        self.assertEqual(sorted(p.name for p in (out / 'assets').iterdir()), sorted(a['fileName'] for a in CONFIG['assets']))
        self.assertEqual(s.m.sha((out / 'inputs/registration.json').read_bytes()), CONFIG['registration']['sha256'])
        with self.assertRaisesRegex(ValueError, 'Preserve'):
            s.materialize(CONFIG, out)

    def test_wrong_identity_member_manifest_and_envelope_pins_rejected(self):
        variants = [dict(CONFIG, **{key: value}) for key, value in (
            ('profile', 'baseline'), ('versionCode', 30319), ('baseVersionCode', 30318),
            ('baseImageSha256', '0' * 64), ('archiveMembersSha256', '0' * 64))]
        for key in ('archive', 'artifact', 'run', 'candidateMetadata', 'verification', 'registration', 'finalImage', 'baseImage'):
            bad = copy.deepcopy(CONFIG)
            bad[key]['sha256'] = '0' * 64
            variants.append(bad)
        for index in range(3):
            bad = copy.deepcopy(CONFIG)
            bad['assets'][index]['sha256'] = '0' * 64
            variants.append(bad)
        for bad in variants:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                s.resolve(bad)

    def test_wrong_protected_run_attempt_source_and_artifact_rejected(self):
        for key, value in (('commitSha', 'a' * 40), ('runId', '1'), ('runAttempt', '2'), ('artifactId', 1)):
            bad = copy.deepcopy(CONFIG)
            bad['originalOwner'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                s.resolve(bad)

    def test_credentials_invalid_input_and_external_output_fail_before_selected_writes(self):
        out = self.folder() / 'not-created'
        with mock.patch.dict(os.environ, {'TRACE_DEPLOY_TOKEN': 'public-double'}), self.assertRaises(ValueError):
            s.materialize(CONFIG, out)
        with self.assertRaises(ValueError):
            s.materialize(dict(CONFIG, versionCode=1), out)
        self.assertFalse(out.exists())
        with self.assertRaises(s.m.host_io.OutputBoundaryError):
            s.materialize(CONFIG, ROOT.parent / 'normal-staging-outside')

    def test_changed_preparation_log_fails_real_read_only_consumer(self):
        out = self.folder() / 'admitted'
        s.materialize(CONFIG, out)
        s.m.checked(out / 'originals/normal/target/steps/patch-apply.stdout.txt').write_bytes(b'not an apply result\n')
        with self.assertRaises(RuntimeError):
            s.verify_preparation(out, json.loads((out / 'inputs/candidate-metadata.json').read_bytes()))


if __name__ == '__main__':
    unittest.main()
