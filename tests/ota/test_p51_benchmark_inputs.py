"""Actual protected-pair admission and early benchmark refusal; no secret or device."""
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
spec = importlib.util.spec_from_file_location('benchmark_test', ROOT / 'Tools/ota/p51-benchmark-inputs.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
RAW = (ROOT / b.MANIFEST).read_bytes()
CONFIG = json.loads(RAW)
AREA = b.m.checked(Path(os.environ.get('P51_TEST_AREA', ROOT / '.cache/p51-benchmark-tests')))


class BenchmarkInputs(unittest.TestCase):
    def folder(self):
        AREA.mkdir(parents=True, exist_ok=True)
        return b.m.checked(Path(tempfile.mkdtemp(prefix='benchmark-', dir=AREA)))

    def context(self, out):
        env = dict(INPUT_CANDIDATE_MODE='archived-benchmark', INPUT_VERSION_NAME='3.3.21',
            INPUT_CANDIDATE_BASE_VERSION='3.3.20', INPUT_PUBLISH='false', INPUT_REHEARSAL='false',
            INPUT_CHECK_BINDINGS='false', INPUT_PACKAGE_CANDIDATE='true', OTA_BOOT_CHAIN_READY='false',
            FIRMWARE_RELEASE_MODE='artifact-candidate-benchmark',
            FIRMWARE_CANDIDATE_CONTEXT='firmware-rehearsal/artifact-only-archived-benchmark-v1',
            GITHUB_ACTIONS='true', GITHUB_EVENT_NAME='workflow_dispatch', GITHUB_REPOSITORY='Eitan-S-23/E-Track',
            GITHUB_SHA='a'*40, GITHUB_WORKFLOW_SHA='a'*40, INPUT_CANDIDATE_REVIEWED_COMMIT='a'*40,
            GITHUB_RUN_ID='1', GITHUB_RUN_ATTEMPT='1', GITHUB_REF='refs/heads/test-benchmark',
            GITHUB_WORKFLOW_REF='Eitan-S-23/E-Track/.github/workflows/firmware-build.yml@refs/heads/test-benchmark')
        owner = dict(commitSha='a'*40, runId='1', runAttempt='1')
        b.m.save_json(out / 'private/owner.json', owner)
        b.m.save_json(out / 'evidence/input-binding.json', dict(owner=owner, manifestSha256=b.m.sha(RAW)))
        return env, owner

    def test_actual_finalized_pair_is_admitted_without_transform(self):
        with mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('no process')), \
                mock.patch.object(b.m, 'source_reference', side_effect=AssertionError('no search')):
            data = b.resolve(CONFIG)
        self.assertEqual(b.m.sha(data['base']), CONFIG['base']['sha256'])
        self.assertEqual(b.m.sha(data['target']), CONFIG['target']['sha256'])
        self.assertEqual([a['bytes'] for a in data['proof']['originalNormalAssets']], [291721, 12439, 615140])
        self.assertEqual(data['proof']['original']['originalOwner']['runId'], '42362540910')
        self.assertEqual(data['proof']['sourceCompilations'], 0)
        self.assertEqual(data['proof']['finalizations'], 0)

    def test_wrong_purpose_versions_and_originals_are_rejected(self):
        for key, value in (('purpose', 'normal-upgrade'), ('baseVersion', '3.3.18'),
            ('targetVersion', '3.3.19'), ('productionPublishable', True),
            ('representativeFunctionalSample', True), ('profile', 'baseline'),
            ('derivation', 'new-source'), ('reference', dict(totalBytes=1048576, seed=7, budget=1000))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                b.resolve(dict(CONFIG, **{key: value}))
        for key in ('normalInputs', 'base', 'target'):
            changed = copy.deepcopy(CONFIG)
            changed[key]['sha256'] = '0'*64
            with self.subTest(key=key), self.assertRaises(ValueError):
                b.resolve(changed)

    def test_materialized_pair_is_write_once_and_verified_again(self):
        out = self.folder()
        b.materialize(RAW, out)
        b.check_materialized(RAW, out)
        with self.assertRaisesRegex(ValueError, 'Preserve'):
            b.materialize(RAW, out)
        b.m.checked(out / 'inputs/base.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'image drift'):
            b.check_materialized(RAW, out)

    def test_missing_or_changed_proof_is_not_admitted(self):
        out = self.folder()
        b.materialize(RAW, out)
        proof = b.m.checked(out / 'inputs/benchmark-source.json')
        proof.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'proof drift'):
            b.check_materialized(RAW, out)
        proof.unlink()
        with self.assertRaises(FileNotFoundError):
            b.check_materialized(RAW, out)

    def test_protected_owner_rejects_context_drift(self):
        out = self.folder()
        env, owner = self.context(out)
        self.assertEqual(b.protected_owner(env, RAW, out), owner)
        for key, value in (('INPUT_PUBLISH', 'true'), ('INPUT_REHEARSAL', 'true'),
            ('INPUT_STAGE_CANDIDATE', 'true'), ('OTA_BOOT_CHAIN_READY', 'true'),
            ('GITHUB_WORKFLOW_SHA', 'b'*40), ('GITHUB_REF', 'refs/tags/test'),
            ('INPUT_CANDIDATE_REVIEWED_COMMIT', 'b'*40), ('GITHUB_RUN_ATTEMPT', '2'),
            ('INPUT_CANDIDATE_BASE_VERSION', '3.3.18'), ('INPUT_RELEASE_NOTES', 'release'),
            ('TRACE_DEPLOY_TOKEN', 'public-test-double')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                b.protected_owner(dict(env, **{key: value}), RAW, out)

    def test_default_key_is_rejected_before_search_or_native_tool(self):
        out = self.folder()
        b.materialize(RAW, out)
        env, _ = self.context(out)
        env['OTA_AES_KEY'] = '00'*16
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(b.m, 'source_reference') as search, \
                mock.patch.object(b.m, 'native_verify') as native, self.assertRaisesRegex(ValueError, 'key binding'):
            b.package(RAW, out, 'not-a-compiler')
        search.assert_not_called()
        native.assert_not_called()
        self.assertFalse((out / 'prepared').exists())

    def test_secret_at_input_or_outside_output_is_rejected_before_write(self):
        out = self.folder() / 'never-created'
        with mock.patch.dict(os.environ, {'OTA_AES_KEY': '00'*16}), self.assertRaises(ValueError):
            b.materialize(RAW, out)
        self.assertFalse(out.exists())
        with self.assertRaises(b.m.host_io.OutputBoundaryError):
            b.materialize(RAW, ROOT.parent / 'benchmark-outside')


if __name__ == '__main__':
    unittest.main()
