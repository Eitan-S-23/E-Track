"""Actual protected-pair admission and early benchmark refusal; no secret or device."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
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
        env = dict(INPUT_CANDIDATE_MODE='archived-benchmark', INPUT_VERSION_NAME=CONFIG['targetVersion'],
            INPUT_CANDIDATE_BASE_VERSION=CONFIG['baseVersion'], INPUT_PUBLISH='false', INPUT_REHEARSAL='false',
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
        self.assertEqual(data['proof']['original']['sourceCommit'], CONFIG['sourceCommit'])
        self.assertEqual(data['proof']['original']['keyedBuildStage'], 'PASS')
        self.assertEqual(data['row']['compressed_sha256'], CONFIG['reference']['stream']['sha256'])
        self.assertEqual(len(data['compressed']) + 104, 1048576)
        self.assertEqual(data['proof']['sourceCompilations'], 0)
        self.assertEqual(data['proof']['finalizations'], 0)

    def test_wrong_purpose_versions_and_originals_are_rejected(self):
        for key, value in (('purpose', 'normal-upgrade'), ('baseVersion', '3.3.18'),
            ('targetVersion', '3.3.19'), ('productionPublishable', True),
            ('representativeFunctionalSample', True), ('profile', 'baseline'),
            ('derivation', 'new-source'), ('reference', dict(totalBytes=1048576, seed=7, budget=1000))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                b.resolve(dict(CONFIG, **{key: value}))
        for key in ('sourceDelivery', 'sourceArchive', 'base', 'target', 'boot'):
            changed = copy.deepcopy(CONFIG)
            changed[key]['sha256'] = '0'*64
            with self.subTest(key=key), self.assertRaises(ValueError):
                b.resolve(changed)

    def test_historical_originals_remain_readable_offline(self):
        historical = dict(CONFIG, schema='p51-benchmark-inputs-v1', baseVersion='3.3.20', targetVersion='3.3.21',
            normalInputs=dict(path='Tools/ota/p51-normal-staging-inputs.json', bytes=2910,
                sha256='196008ecdfa7be4244f0d7d937666454a6d5126a618a7fae516ba2a0aea2cd7e'),
            base=dict(bytes=614092, sha256='5d86c6b3de6535004b4aef2333706511a27cb194b8353712684c9bcc17725741'),
            target=dict(bytes=615132, sha256='1564ccee0a9a6bc019d8877fc832c7542c2e815ce05412b6511bf9f724936af3'),
            reference=dict(totalBytes=1048576, seed=7, budget=256))
        data = b.resolve(historical)
        self.assertEqual(data['proof']['original']['originalOwner']['runId'], '42362540910')
        self.assertEqual([a['bytes'] for a in data['proof']['originalNormalAssets']], [291721, 12439, 615140])

    def test_failed_keyed_build_is_rejected_even_with_matching_archive_digest(self):
        read = b.m.read
        with zipfile.ZipFile(io.BytesIO(read(CONFIG['sourceArchive']))) as original:
            files = {row.filename: original.read(row) for row in original.infolist()}
        evidence = json.loads(files['keyed-build/keyed-build-evidence.json'])
        evidence['steps'][1]['exitCode'] = 1
        files['keyed-build/keyed-build-evidence.json'] = json.dumps(evidence).encode()
        files['keyed-build/steps.json'] = json.dumps(evidence['steps']).encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in files.items():
                archive.writestr(name, data)
        raw = output.getvalue()
        delivery = json.loads(read(CONFIG['sourceDelivery']))
        delivery['artifact'].update(digest='sha256:' + b.m.sha(raw), size_in_bytes=len(raw))
        def altered(pin):
            if pin == CONFIG['sourceArchive']:
                return raw
            if pin == CONFIG['sourceDelivery']:
                return json.dumps(delivery).encode()
            return read(pin)
        with mock.patch.object(b.m, 'read', side_effect=altered), self.assertRaisesRegex(ValueError, 'build stage'):
            b.resolve(CONFIG)

    def test_reference_metadata_and_raw_stream_are_both_checked(self):
        base, target = (b.m.read(CONFIG[key]) for key in ('base', 'target'))
        read = b.m.read
        original = json.loads(read(CONFIG['reference']['selection']))
        for key, value in (('seed', 7), ('count', -1), ('salt', 65536), ('props_hex', '0000000000'),
            ('base_sha256', '0'*64), ('target_sha256', '0'*64), ('raw_sha256', '0'*64)):
            changed = json.dumps(dict(original, **{key: value})).encode()
            def altered(pin):
                return changed if pin == CONFIG['reference']['selection'] else read(pin)
            with self.subTest(key=key), mock.patch.object(b.m, 'read', side_effect=altered), \
                    self.assertRaises((ValueError, AssertionError)):
                b.reference_input(base, target, CONFIG)
        changed = copy.deepcopy(CONFIG)
        changed['reference']['stream']['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            b.reference_input(base, target, changed)

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
