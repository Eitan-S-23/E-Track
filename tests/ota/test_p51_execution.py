"""Admission and phone-original guards for the P5 execution adapter."""
from pathlib import Path
import copy
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import run
import observation as obs
import pipeline_cloud as cloud


class FunctionalSampleGuards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = run.h.checked(Path(os.environ.get('P51_TEST_AREA', ROOT / '.cache/p51-functional-sample-tests')))
        parent.mkdir(parents=True, exist_ok=True)
        cls.area = run.h.checked(Path(tempfile.mkdtemp(prefix='normal-', dir=parent)))
        env = run.h.environment(cls.area)
        for key in list(env):
            if key.startswith(('OTA_', 'TRACE_', 'CF_', 'CLOUDFLARE_', 'GH_', 'GITHUB_', 'P35_')):
                del env[key]
        for key in ('SSLKEYLOGFILE', 'NODE_OPTIONS', 'NODE_V8_COVERAGE'):
            env.pop(key, None)
        env.update(PYTHON=sys.executable, NODE_DISABLE_COMPILE_CACHE='1')
        cls.templates = {}
        for label in ('normal', 'header-only'):
            out = run.h.checked(cls.area / label)
            raw = run.h.command(cls.area, 'prepare-' + label, [shutil.which('node', path=env.get('PATH')),
                ROOT / 'tests/ota/p51_preparation_fixture.mjs', out, label], env, seconds=120)
            cls.templates[label] = json.loads(raw)

    def setUp(self):
        self.root = run.h.fresh(self.area / self._testMethodName)
        self.prepared = run.h.checked(self.root / 'prepared')
        shutil.copytree(self.templates['normal']['prepared'], self.prepared)
        self.sequence = 0
        self.proof = run.h.read_json(self.prepared / 'verification.json')
        base = run.h.record(self.prepared / 'work/base-final.bin')
        target = run.h.record(self.prepared / 'app-final.bin')
        self.old = (ROOT / base['path']).read_bytes()
        full, packet = (run.h.record(self.prepared / next(a['fileName'] for a in self.proof['assets'] if a['kind'] == kind))
                        for kind in ('full', 'patch'))
        self.plan = dict(kind='patch', mcu=dict(package=packet,
            images=dict(base=dict(image=base), target=dict(image=target))),
            functional_sample=dict(purpose='normal-upgrade', full_package=full),
            tool_dependencies=[run.h.record(Path(self.templates['normal']['tool']))])
        self.bind_proof()

    def pin(self, name, data):
        path = run.h.checked(self.root / name)
        path.write_bytes(data)
        return run.h.record(path)

    def bind_proof(self):
        self.sequence += 1
        self.plan['functional_sample']['preparation'] = self.pin('prepared/proof-%d.json' % self.sequence,
            json.dumps(self.proof).encode('ascii'))

    def replace_package(self, kind, data):
        asset = next(row for row in self.proof['assets'] if row['kind'] == kind)
        pin = self.pin('prepared/' + asset['fileName'], data)
        asset.update(sizeBytes=pin['bytes'], sha256=pin['sha256'])
        if kind == 'patch':
            self.plan['mcu']['package'] = pin
        else:
            self.plan['functional_sample']['full_package'] = pin
        full, packet = self.plan['functional_sample']['full_package'], self.plan['mcu']['package']
        self.proof['patchComparison'].update(fullPackageBytes=full['bytes'], patchPackageBytes=packet['bytes'],
            savedBytes=full['bytes']-packet['bytes'], savingsRatio=(full['bytes']-packet['bytes'])/full['bytes'])
        self.bind_proof()

    def replace_step(self, label, *, log=None):
        step = next(row for row in self.proof['steps'] if row['label'] == label)
        if log is not None:
            pin = self.pin('prepared/steps/' + label + '.stdout.txt', log)
            step['stdoutSha256'] = pin['sha256']
        self.pin('prepared/steps.json', json.dumps(self.proof['steps']).encode('ascii'))
        self.bind_proof()

    def test_bound_normal_smaller_real_change_is_admitted(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(run.h, 'command', side_effect=AssertionError('admission must not repackage or spawn')):
            run.validate_functional_patch(self.plan)

    def test_reference_or_unlabelled_input_is_rejected(self):
        for value in (None, {}, dict(purpose='fixed-load-benchmark'), dict(purpose='normal-upgrade-diagnostic')):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                run.validate_functional_patch(dict(self.plan, functional_sample=value))

    def test_false_or_non_normal_preparation_does_not_admit(self):
        original = copy.deepcopy(self.proof)
        for key, value in (('packagePurpose', 'fixed-load-benchmark'), ('packagePurpose', 'normal-upgrade-diagnostic'),
                           ('ok', False), ('fullByteEqual', False), ('patchByteEqual', False)):
            self.proof = dict(original, **{key: value})
            self.bind_proof()
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                run.validate_functional_patch(self.plan)

    def test_receipt_must_be_an_object_and_use_registration_base_identity(self):
        original = copy.deepcopy(self.proof)
        for value in (None, [], 'success'):
            self.proof = value
            self.bind_proof()
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                run.validate_functional_patch(self.plan)
        self.proof = original
        self.proof['assets'][0]['baseImageSha256'] = None
        self.bind_proof()
        with self.assertRaisesRegex(RuntimeError, 'base identity'):
            run.validate_functional_patch(self.plan)

    def test_equal_or_larger_patch_rejected_even_with_consistent_size_receipt(self):
        packet = self.plan['mcu']['package']
        for size in (packet['bytes'], packet['bytes']-1):
            full = self.pin('full-%d.etu' % size, b'F' * size)
            self.plan['functional_sample']['full_package'] = full
            self.proof['assets'][0].update(sizeBytes=size, sha256=full['sha256'])
            self.proof['patchComparison'].update(fullPackageBytes=size, savedBytes=size-packet['bytes'],
                                                 preferredKindForMatchingBase='full')
            self.bind_proof()
            with self.subTest(size=size), self.assertRaisesRegex(RuntimeError, 'smaller'):
                run.validate_functional_patch(self.plan)

    def test_modified_package_bytes_rejected(self):
        packet = self.plan['mcu']['package']
        (ROOT / packet['path']).write_bytes(b'X' * packet['bytes'])
        with self.assertRaisesRegex(RuntimeError, 'input identity mismatch'):
            run.validate_functional_patch(self.plan)

    def test_header_only_rejected_despite_claimed_source_change(self):
        target = bytearray(self.old)
        target[0x408] ^= 1
        pin = self.pin('header-only.bin', bytes(target))
        self.plan['mcu']['images']['target']['image'] = pin
        self.proof['finalImage'].update(sha256=pin['sha256'], sizeBytes=pin['bytes'])
        self.proof['patchComparison']['targetImageSha256'] = pin['sha256']
        self.bind_proof()
        with self.assertRaisesRegex(RuntimeError, 'header-only'):
            run.validate_functional_patch(self.plan)

    def test_genuine_header_only_preparation_remains_a_boundary_sample(self):
        original = Path(self.templates['header-only']['prepared'])
        proof = run.h.read_json(original / 'verification.json')
        plan = copy.deepcopy(self.plan)
        plan['mcu']['images'] = dict(base=dict(image=run.h.record(original / 'work/base-final.bin')),
                                   target=dict(image=run.h.record(original / 'app-final.bin')))
        plan['mcu']['package'] = run.h.record(original / next(a['fileName'] for a in proof['assets'] if a['kind'] == 'patch'))
        plan['functional_sample'] = dict(purpose='normal-upgrade', preparation=run.h.record(original / 'verification.json'),
            full_package=run.h.record(original / next(a['fileName'] for a in proof['assets'] if a['kind'] == 'full')))
        with self.assertRaisesRegex(RuntimeError, 'header-only'):
            run.validate_functional_patch(plan)

    def test_missing_tool_and_command_evidence_is_rejected(self):
        original = copy.deepcopy(self.proof)
        for field in ('tool', 'steps'):
            self.proof = copy.deepcopy(original)
            del (self.proof['patchComparison'] if field == 'tool' else self.proof)[field]
            self.bind_proof()
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                run.validate_functional_patch(self.plan)

    def test_tool_identity_must_bind_an_actual_dependency(self):
        for value in ([], [dict(self.plan['tool_dependencies'][0], sha256='0'*64)]):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                run.validate_functional_patch(dict(self.plan, tool_dependencies=value))

    def test_non_etu_rejected_despite_rebound_digest_and_size(self):
        self.replace_package('patch', b'not-an-etu')
        with self.assertRaises(RuntimeError):
            run.validate_functional_patch(self.plan)

    def test_actual_package_identity_and_integrity_not_claims(self):
        for kind, offset, size, value in (
            ('patch', 44, 4, 20802), ('patch', 52, 8, 0), ('full', 40, 4, 20802),
            ('full', 6, 2, 7), ('patch', 6, 2, 11), ('patch', 12, 4, 2),
            ('patch', 8, 4, 2), ('patch', 48, 2, 2), ('patch', 50, 1, 2), ('patch', 51, 1, 2)):
            pin = self.plan['mcu']['package'] if kind == 'patch' else self.plan['functional_sample']['full_package']
            original = (ROOT / pin['path']).read_bytes()
            changed = bytearray(original)
            changed[offset:offset+size] = value.to_bytes(size, 'little')
            struct.pack_into('<I', changed, 60, zlib.crc32(changed[:60]))
            self.replace_package(kind, bytes(changed))
            with self.subTest(kind=kind, offset=offset), self.assertRaisesRegex(RuntimeError, 'ETU'):
                run.validate_functional_patch(self.plan)
            self.replace_package(kind, original)

    def test_actual_crc_truncation_and_trailing_bytes_rejected(self):
        original = (ROOT / self.plan['mcu']['package']['path']).read_bytes()
        header = bytearray(original); header[60] ^= 1
        payload = bytearray(original); payload[-1] ^= 1
        for changed in (bytes(header), bytes(payload), original[:-1], original+b'trailer'):
            self.replace_package('patch', changed)
            with self.subTest(length=len(changed)), self.assertRaises(RuntimeError):
                run.validate_functional_patch(self.plan)

    def test_complete_original_receipts_are_required(self):
        for relative in ('steps.json', 'steps/patch-apply.stdout.txt', 'steps/full-pack.stderr.txt',
                         'work/patch-candidate.bin', 'work/full-candidate.bin', 'cloudflare-firmware-release-metadata.json'):
            path = self.prepared / relative
            raw = path.read_bytes()
            path.unlink()
            with self.subTest(relative=relative), self.assertRaises(RuntimeError):
                run.validate_functional_patch(self.plan)
            path.write_bytes(raw)

    def test_changed_applied_candidate_is_not_hidden_by_true_boolean(self):
        self.pin('prepared/work/patch-candidate.bin', b'not the verified target')
        with self.assertRaises(RuntimeError):
            run.validate_functional_patch(self.plan)

    def test_original_log_drift_and_false_success_are_rejected(self):
        self.pin('prepared/steps/patch-apply.stdout.txt', b'unpack(patch) OK: fake\n')
        with self.assertRaises(RuntimeError):
            run.validate_functional_patch(self.plan)
        self.replace_step('patch-apply', log=b'unpack(patch) OK: fake\n')
        with self.assertRaises(RuntimeError):
            run.validate_functional_patch(self.plan)

    def test_wrong_command_input_or_duplicate_step_is_rejected(self):
        steps = copy.deepcopy(self.proof['steps'])
        for label, flag in (('patch-pack', '--old'), ('patch-apply', '--old'), ('full-pack', '--app')):
            self.proof['steps'] = copy.deepcopy(steps)
            step = next(row for row in self.proof['steps'] if row['label'] == label)
            step['argv'][step['argv'].index(flag)+1] += '.wrong'
            self.replace_step(label)
            with self.subTest(label=label), self.assertRaises(RuntimeError):
                run.validate_functional_patch(self.plan)
        self.proof['steps'] = [*steps, steps[0]]
        self.replace_step('base-verify')
        with self.assertRaises(RuntimeError):
            run.validate_functional_patch(self.plan)

    def test_wrong_verified_json_is_rejected_even_with_rebound_stdout_digest(self):
        fields = json.loads((self.prepared / 'steps/patch-outer-verify.stdout.txt').read_bytes())
        fields['sha256'] = '0'*64
        self.replace_step('patch-outer-verify', log=json.dumps(fields).encode('ascii'))
        with self.assertRaises(RuntimeError):
            run.validate_functional_patch(self.plan)

    def test_gate_failures_precede_channel_and_device_ownership(self):
        argv = ['run.py', 'cell', '--inputs', '.cache/input.json', '--out', '.cache/not-created',
                '--contract', 'docs/contract.json', '--matrix', '.cache/matrix.json', '--command-id', 'BLE-PATCH']
        original = copy.deepcopy(self.plan)
        self.replace_package('patch', b'not-an-etu')
        for plan in (dict(original, functional_sample={}), self.plan):
            with patch.object(sys, 'argv', argv), patch.object(run.h, 'read_json', wraps=run.h.read_json) as read, \
                    patch.object(run, 'validate', return_value=plan), patch.object(run.h, 'record', return_value={}), \
                    patch.object(run.h, 'fresh', return_value=ROOT / '.cache/not-created'), patch.object(run.h, 'save'), \
                    patch.object(run, 'gate'), \
                    patch.object(run.h, 'device_owner', side_effect=RuntimeError('unexpected device ownership')) as owner, \
                    patch.object(run, 'channel', side_effect=RuntimeError('unexpected channel ownership')) as channel, \
                    patch.object(run, 'cell', side_effect=AssertionError('device code must never run')), self.assertRaises(RuntimeError):
                read.side_effect = lambda p: {} if Path(p).name == 'input.json' else json.loads(Path(p).read_bytes())
                run.main()
            owner.assert_not_called()
            channel.assert_not_called()

    def test_mismatched_asset_target_base_or_encoding_rejected(self):
        original = copy.deepcopy(self.proof)
        changes = [('asset', 'sha256', 'f'*64), ('base', 'imageSha256', 'f'*64),
                   ('finalImage', 'sha256', 'f'*64), ('patchComparison', 'encoding', 'size-target-search'),
                   ('patchComparison', 'savedBytes', 0), ('patchComparison', 'patchPackageBytes', 1)]
        for section, field, value in changes:
            self.proof = copy.deepcopy(original)
            row = self.proof['assets'][1] if section == 'asset' else self.proof[section]
            row[field] = value
            self.bind_proof()
            with self.subTest(section=section, field=field), self.assertRaises(RuntimeError):
                run.validate_functional_patch(self.plan)

    def test_full_does_not_need_a_patch_receipt(self):
        run.validate_functional_patch(dict(kind='full'))

    def test_cli_rejects_legacy_reference_before_channel_or_device_ownership(self):
        argv = ['run.py', 'cell', '--inputs', '.cache/input.json', '--out', '.cache/not-created',
                '--contract', 'docs/contract.json', '--matrix', '.cache/matrix.json', '--command-id', 'BLE-PATCH']
        with patch.object(sys, 'argv', argv), patch.object(run.h, 'read_json', return_value={}), \
                patch.object(run, 'validate', return_value=dict(kind='patch')), patch.object(run.h, 'record', return_value={}), \
                patch.object(run.h, 'fresh', return_value=ROOT / '.cache/not-created'), patch.object(run.h, 'save'), \
                patch.object(run, 'gate'), patch.object(run.h, 'device_owner') as owner, \
                patch.object(run, 'channel') as channel, self.assertRaisesRegex(RuntimeError, 'normal-upgrade'):
            run.main()
        owner.assert_not_called()
        channel.assert_not_called()


class ExecutionGuards(unittest.TestCase):
    def test_p5_uses_explicit_bounded_stream_idle_window(self):
        driver = object.__new__(obs.Observer)
        with patch.object(obs.r.Android, 'start_live_stream', return_value='started') as start:
            self.assertEqual(driver.start_live_stream(), 'started')
        start.assert_called_once_with(driver, idle_seconds=60)

    def test_known_null_root_has_bounded_read_only_recovery(self):
        driver = object.__new__(obs.Observer)
        driver.p, driver.pid = dict(app=dict(id='test.pkg')), '7305'
        null = b'ERROR: null root node returned by UiTestAutomationBridge.\n'
        valid = b'<hierarchy><node package="test.pkg"/></hierarchy>'
        responses = [item for raw in (null, null, valid) for item in (b'7305', b'window', raw, b'window', b'7305')]
        with patch.object(driver, 'cmd', side_effect=responses) as cmd, patch.object(driver, 'record') as record, \
                patch.object(obs.r, 'foreground_ok', return_value=True):
            self.assertEqual(driver.ui(), valid)
        self.assertEqual(cmd.call_count, 15)
        self.assertEqual(record.call_count, 2)
        self.assertTrue(all(call.args[0][0] in ('shell', 'exec-out') for call in cmd.call_args_list))

    def test_persistent_null_or_other_missing_hierarchy_still_fails(self):
        driver = object.__new__(obs.Observer)
        driver.p, driver.pid = dict(app=dict(id='test.pkg')), '7305'
        for raw, count in ((b'ERROR: null root node returned by UiTestAutomationBridge.', 3), (b'unknown failure', 1)):
            responses = [item for _ in range(count) for item in (b'7305', b'window', raw, b'window', b'7305')]
            with patch.object(driver, 'cmd', side_effect=responses) as cmd, patch.object(driver, 'record'), \
                    patch.object(obs.r, 'foreground_ok', return_value=True), self.assertRaises(obs.r.Stop):
                driver.ui()
            self.assertEqual(cmd.call_count, 5*count)

    def test_real_cli_normalizes_relative_input_before_recording(self):
        argv = ['run.py', 'cell', '--inputs', '.cache/input.json', '--out', '.cache/not-created',
                '--contract', 'docs/contract.json', '--matrix', '.cache/matrix.json', '--command-id', 'SD-FULL']
        def record(path):
            self.assertEqual(path, ROOT / '.cache/input.json')
            return {}
        with patch.object(sys, 'argv', argv), patch.object(run.h, 'read_json', return_value={}), \
                patch.object(run, 'validate', return_value={}), patch.object(run.h, 'record', side_effect=record), \
                patch.object(run.h, 'fresh', return_value=ROOT / '.cache/not-created'), patch.object(run.h, 'save'), \
                patch.object(run, 'gate', side_effect=RuntimeError('stop before device')) as gate, \
                patch.object(run.m, 'MCU') as mcu, self.assertRaisesRegex(RuntimeError, 'stop before device'):
            run.main()
        gate.assert_called_once()
        mcu.assert_not_called()

    def test_successor_requires_pinned_actual_predecessor(self):
        self.assertEqual(run.predecessor_arguments({'version': 1}), [])
        with self.assertRaises(RuntimeError):
            run.predecessor_arguments({'version': 2})
        prior = dict(contract={'path': 'first'}, matrix={'path': 'second'})
        with patch.object(run.h, 'pinned', side_effect=lambda pin: pin['path']):
            self.assertEqual(run.predecessor_arguments(dict(version=2, predecessor_bundle=prior)),
                             ['--previous-contract', 'first', '--previous-matrix', 'second'])

    def test_original_reuse_sources_are_forwarded_without_skipping_predecessor(self):
        prior = dict(contract={'path': 'previous-contract'}, matrix={'path': 'previous-matrix'})
        origin = dict(contract={'path': 'origin-contract'}, matrix={'path': 'origin-matrix'})
        with patch.object(run.h, 'pinned', side_effect=lambda pin: pin['path']):
            self.assertEqual(run.predecessor_arguments(dict(version=7, predecessor_bundle=prior, reuse_sources=[origin])),
                ['--previous-contract', 'previous-contract', '--previous-matrix', 'previous-matrix',
                 '--reuse-source', 'origin-contract', 'origin-matrix'])
            for sources in ('unbound', [{'contract': origin['contract']}], [None]):
                with self.subTest(sources=sources), self.assertRaises(RuntimeError):
                    run.predecessor_arguments(dict(version=7, predecessor_bundle=prior, reuse_sources=sources))

    def test_previous_cell_path_is_absolute_before_any_device_operation(self):
        argv = ['run.py', 'restore', '--inputs', '.cache/input.json', '--out', '.cache/not-created',
                '--previous', '.cache/previous-cell', '--contract', 'docs/contract.json',
                '--matrix', '.cache/matrix.json', '--command-id', 'RESTORE-BLE-FULL']
        def gate(args, out):
            self.assertEqual(args.previous, ROOT / '.cache/previous-cell')
            raise RuntimeError('stop before device')
        with patch.object(sys, 'argv', argv), patch.object(run.h, 'read_json', return_value={}), \
                patch.object(run, 'validate', return_value={}), patch.object(run.h, 'record', return_value={}), \
                patch.object(run.h, 'fresh', return_value=ROOT / '.cache/not-created'), patch.object(run.h, 'save'), \
                patch.object(run, 'gate', side_effect=gate), patch.object(run.m, 'MCU') as mcu, \
                self.assertRaisesRegex(RuntimeError, 'stop before device'):
            run.main()
        mcu.assert_not_called()

    def test_identity_step_asks_immediately_only_when_required_event_is_missing(self):
        image = dict(version=30317, sha256='a'*64)
        for present in (None, {'event': 'identity'}):
            driver = object.__new__(obs.Observer)
            driver.p, driver.live = dict(device=dict(address='e3:49:e1:14:d6:cb')), []
            with patch.object(driver, 'phase'), patch.object(driver, 'pump_stream') as pump, \
                    patch.object(driver, 'ask') as ask, patch.object(driver, 'wait', return_value={'seq': 9}), \
                    patch.object(driver, 'record'), patch.object(obs, 'identity', return_value=present):
                self.assertEqual(driver.fresh_identity(image, request=True), {'seq': 9})
                pump.assert_called_once()
                self.assertEqual(ask.call_count, int(present is None))

    def test_cloud_proxy_is_explicit_bound_connect_with_target_tls(self):
        context = object()
        with patch.object(cloud.http.client, 'HTTPSConnection') as connection:
            direct = cloud.Cloud({}, Path('.cache/not-created'), None)
            direct.connect(cloud.ADMIN, context)
            connection.assert_called_once_with('e-track-firmware-p43-admin-test.pages.dev', timeout=25, context=context)
            connection.return_value.set_tunnel.assert_not_called()
            connection.reset_mock()
            proxied = cloud.Cloud({'https_proxy': 'http://127.0.0.1:7897'}, Path('.cache/not-created'), None)
            proxied.connect(cloud.ADMIN, context)
            connection.assert_called_once_with('127.0.0.1', 7897, timeout=25, context=context)
            connection.return_value.set_tunnel.assert_called_once_with('e-track-firmware-p43-admin-test.pages.dev', 443)
            for value in ('http://elsewhere:7897', 'http://127.0.0.1:80', 'http://user:pass@127.0.0.1:7897'):
                with self.subTest(value=value), self.assertRaises(Exception):
                    cloud.Cloud({'https_proxy': value}, Path('.cache/not-created'), None).connect(cloud.ADMIN, context)

    def test_exact_frozen_arguments(self):
        argv = ['cell', '--inputs', '.cache/in.json', '--out', '.cache/out', '--channel', 'sd',
                '--contract', 'docs/c.json', '--matrix', '.cache/m.json', '--command-id', 'sd-full']
        command = 'python -I -S -B -X utf8 Tools/ota/p51-acceptance/run.py ' + ' '.join(argv)
        run.invocation(command, argv)
        for old, new in (('sd-full', 'ble-full'), ('--channel sd', '--channel ble'),
                         ('--out .cache/out', '--out .cache/other'), ('-I -S', '-S -I')):
            with self.subTest(old=old), self.assertRaises(RuntimeError):
                run.invocation(command.replace(old, new), argv)

    def test_ui_actions_never_automated(self):
        for method in (obs.Observer.tap, obs.Observer.scroll):
            with self.assertRaises(RuntimeError):
                method(None)

    def test_identity_requires_post_boundary_real_event(self):
        row = dict(seq=3, event='identity', deviceAddress='e3:49:e1:14:d6:cb',
            linkConnected=True, freshConnection=True, currentVersionCode=30319,
            currentImageSha256='a'*64)
        self.assertEqual(obs.identity([row], 30319, 'a'*64, row['deviceAddress'], 2), row)
        for change in ({'event': 'heartbeat'}, {'seq': 2}, {'currentVersionCode': 30317},
                       {'currentImageSha256': 'b'*64}):
            self.assertIsNone(obs.identity([dict(row, **change)], 30319, 'a'*64, row['deviceAddress'], 2))
        for change in ({'linkConnected': False}, {'freshConnection': False}, {'deviceAddress': '00:00:00:00:00:00'}):
            with self.assertRaises(RuntimeError):
                obs.identity([dict(row, **change)], 30319, 'a'*64, row['deviceAddress'], 2)

    def test_sd_never_mutates_channels(self):
        with run.channel({}, Path('.cache/not-created'), False):
            pass

    def test_restore_rejects_missing_result_before_constructing_mcu(self):
        with patch.object(run.m, 'MCU') as mcu, self.assertRaises(RuntimeError):
            run.restore({}, Path('.cache/not-created'), None)
        mcu.assert_not_called()

    def test_recording_failure_does_not_restart_a_transfer(self):
        fake = object.__new__(obs.Observer)
        fake.capture_id = None
        fake.capture_resolved = False
        with patch.object(fake, 'cmd') as command:
            fake.preserve_failure()
        command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
