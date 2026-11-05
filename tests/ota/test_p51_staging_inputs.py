"""Actual original archive and parser; no key, compiler, package or cloud calls."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('p51_staging', ROOT / 'Tools/ota/p51-staging-inputs.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
AREA = s.m.checked(Path(os.environ.get('P51_TEST_AREA', ROOT / '.cache/p51-staging/selftests')))
CONFIG = json.loads((ROOT / 'Tools/ota/p51-staging-inputs.json').read_bytes())


class StagingInputs(unittest.TestCase):
    def folder(self):
        AREA.mkdir(parents=True, exist_ok=True)
        return s.m.checked(Path(tempfile.mkdtemp(prefix='staging-', dir=AREA)))

    def test_original_assets_and_all_forbidden_transform_calls_are_zero(self):
        with mock.patch.object(s.m, 'package', side_effect=AssertionError('no packaging')), \
             mock.patch.object(s.m, 'package_supplement', side_effect=AssertionError('no initialization')), \
             mock.patch.object(s.m, 'source_images', side_effect=AssertionError('no finalization')), \
             mock.patch.object(s.m, 'source_reference', side_effect=AssertionError('no witness')), \
             mock.patch.object(s.m, 'native_verify', side_effect=AssertionError('no compiler')), \
             mock.patch.object(s.m, 'envelope', side_effect=AssertionError('no encryption')), \
             mock.patch.object(s.m.encoding, 'search_adaptive', side_effect=AssertionError('no search')):
            data = s.resolve_staging(CONFIG)
            self.assertEqual([s.m.sha(blob) for blob in data['blobs']], [a['sha256'] for a in CONFIG['assets']])
            self.assertEqual(data['proof']['originalOwner'], dict(commitSha='1430c8ff7f3bcd9a35bfe158ba697b99021f75f2',
                runId='41900439548', runAttempt='1', artifactId=13359301400, buildTimestamp=1793820855))

    def test_materializes_only_three_assets_without_changing_original_metadata(self):
        folder = self.folder() / 'outputs'
        s.materialize(CONFIG, folder)
        self.assertEqual(sorted(p.name for p in (folder / 'assets').iterdir()), sorted(a['fileName'] for a in CONFIG['assets']))
        meta = (folder / 'inputs/candidate-metadata.json').read_bytes()
        self.assertEqual(s.m.sha(meta), 'd0ac413335eb8bd77838e4ec8ca305c411a4f517b6d03b1f06746c1e1e73ce96')
        self.assertFalse(json.loads(meta)['readyRegistered'])
        with self.assertRaisesRegex(ValueError, 'Preserve'):
            s.materialize(CONFIG, folder)

    def test_target_base_profile_and_asset_digest_mismatch_rejected(self):
        bads = []
        for key, value in [('versionCode',30320), ('baseVersionCode',30317), ('baseImageSha256','0'*64), ('profile','baseline')]:
            bads.append(dict(CONFIG, **{key:value}))
        for key in ('finalImage', 'verification'):
            bad = copy.deepcopy(CONFIG)
            bad[key]['sha256'] = '0'*64
            bads.append(bad)
        for index in range(3):
            bad = copy.deepcopy(CONFIG)
            bad['assets'][index]['sha256'] = '0'*64
            bads.append(bad)
        for config in bads:
            with self.subTest(config=config), self.assertRaises(ValueError):
                s.resolve_staging(config)

    def test_wrong_archive_source_run_attempt_and_artifact_rejected(self):
        original = json.loads(s.m.read(CONFIG['sourceInputs']))
        folder = self.folder()
        variants = [dict(original, **{key:value}) for key, value in [('sourceCommit','a'*40), ('originalRun',1),
                    ('originalAttempt',2), ('originalArtifact',1), ('buildTimestamp',1)]]
        bad = copy.deepcopy(original)
        bad['archive']['sha256'] = '0'*64
        variants.append(bad)
        for index, changed in enumerate(variants):
            file = folder / ('source-%d.json' % index)
            s.m.save_json(file, changed)
            record = dict(path=file.relative_to(ROOT).as_posix(), bytes=file.stat().st_size, sha256=s.m.sha(file.read_bytes()))
            with self.subTest(index=index), self.assertRaises(ValueError):
                s.resolve_staging(dict(CONFIG, sourceInputs=record))

    def test_rejection_creates_no_selected_output_and_rejects_credentials(self):
        folder = self.folder()
        bad = dict(CONFIG, profile='baseline')
        with self.assertRaises(ValueError):
            s.materialize(bad, folder / 'not-created')
        self.assertFalse((folder / 'not-created').exists())
        with mock.patch.dict(s.os.environ, {'TRACE_DEPLOY_TOKEN':'public-noncredential-double'}), self.assertRaises(ValueError):
            s.materialize(CONFIG, folder / 'not-created')
        self.assertFalse((folder / 'not-created').exists())

    def test_output_boundary_rejects_sibling_before_any_file_creation(self):
        with self.assertRaises(s.m.host_io.OutputBoundaryError):
            s.materialize(CONFIG, ROOT.parent / 'outside-staging-test')


if __name__ == '__main__':
    unittest.main()
