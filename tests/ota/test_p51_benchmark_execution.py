"""P51 benchmark lifecycle/capacity/fixture oracles; every device is a test double."""
from collections import deque
import copy
import fnmatch
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qsl, urlsplit
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import benchmark as b
import fixture
import run
h, r = b.h, b.r


def firmware():
    return dict(device_address='e3:49:e1:14:d6:cb', protocol=2,
        current=dict(version=30320, sha256='a'*64), target=dict(version=30321, sha256='b'*64),
        package=dict(bytes=1048576, sha256='c'*64), release_id='p51-benchmark-30320-30321',
        latest_url='https://fixture.trycloudflare.com/api/public/firmware/latest')


def state(fw, *, target=False, idle=False, seq=1):
    image = fw['target' if target else 'current']
    return dict(seq=seq, event='identity', phase='idle' if idle else 'completed' if target else 'readyToInstall',
        deviceAddress=fw['device_address'], currentVersionCode=image['version'], currentImageSha256=image['sha256'],
        targetVersionCode=None if idle else fw['target']['version'], targetImageSha256=None if idle else fw['target']['sha256'],
        packageSha256=None if idle else fw['package']['sha256'], packageBytes=0 if idle else 1048576,
        packageVerified=not idle, releaseId=None if idle else fw['release_id'], latestUrl=fw['latest_url'],
        protocol=None if idle else 2, session=0 if idle or not target else 1, durable=0 if idle or not target else 1048576,
        freshConnection=True, linkConnected=True, healthy=True)


def sealed_capture(cid):
    row = state(firmware(), idle=True)
    row.update(schema=1, captureId=cid, monoUs=1, targetVersionCode=0,
        bitmap=None, sendOffset=None, lost=0, error=None)
    r.validate_state(row)
    body = ('OTA_P35_STATE '+json.dumps(row)+'\n').encode()
    opened = dict(schema=1, kind='open', captureId=cid)
    closed = dict(schema=1, kind='close', captureId=cid, records=1,
        sha256=hashlib.sha256(body).hexdigest(), healthy=True, lost=0, error=None)
    return ('OTA_P35_CAPTURE '+json.dumps(opened)+'\n').encode()+body+('OTA_P35_CAPTURE '+json.dumps(closed)+'\n').encode()


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        parent = h.checked(Path(os.environ.get('P51_TEST_AREA', ROOT / '.cache/p51-benchmark-execution-tests')))
        parent.mkdir(parents=True, exist_ok=True)
        self.out = h.checked(Path(tempfile.mkdtemp(prefix='execution-', dir=parent)))
        self.fw = firmware()

    def driver(self):
        driver = object.__new__(b.Observer)
        driver.p = dict(app=dict(id=b.APP_ID), limits=dict(event_seconds=10),
            ui={name: {'resource-id': 'p35-' + name} for name in ('start', 'resume', 'stop')})
        driver.capture_id, driver.arm_attempted = 'd'*32, True
        driver.mutation_unknown, driver.transfer_start_attempted = False, False
        driver.preparation, driver.firmware = driver, self.fw
        driver.live = [state(self.fw)]
        driver.queue, driver.last_state_at = deque([driver.live[-1]]), time.monotonic()
        driver.record, driver.pump, driver.phase, driver.idle_services = Mock(), Mock(), Mock(), Mock()
        driver.cmd = Mock(return_value=b'')
        return driver

    def xml(self, *, package=b.APP_ID, enabled='true'):
        return ('<hierarchy><node package="%s" resource-id="p35-start" enabled="%s" '
            'clickable="true" bounds="[10,20][30,40]"/></hierarchy>' % (package, enabled)).encode()

    def test_existing_semantic_driver_taps_exactly_once_then_refuses_uncertainty(self):
        driver = self.driver()
        driver.ui = Mock(return_value=self.xml())
        driver.tap({'resource-id': 'p35-start'})
        driver.cmd.assert_called_once_with(['shell', 'input', 'tap', '20', '30'], seconds=5)
        self.assertTrue(driver.transfer_start_attempted)
        self.assertTrue(driver.mutation_unknown)
        with self.assertRaisesRegex(RuntimeError, 'unresolved'):
            driver.tap({'resource-id': 'p35-start'})
        self.assertEqual(driver.cmd.call_count, 1)

    def test_foreign_and_disabled_control_never_tap(self):
        for package, enabled in (('foreign.pkg', 'true'), (b.APP_ID, 'false')):
            driver = self.driver()
            driver.ui = Mock(return_value=self.xml(package=package, enabled=enabled))
            with self.subTest(package=package, enabled=enabled), patch.object(r.time, 'sleep'), self.assertRaises(r.Stop):
                driver.tap({'resource-id': 'p35-start'})
            driver.cmd.assert_not_called()

    def test_wrong_package_binding_or_expired_heartbeat_never_starts(self):
        driver = self.driver()
        driver.ui = Mock(return_value=self.xml())
        driver.live[-1]['packageSha256'] = 'f'*64
        with self.assertRaises(r.Stop):
            driver.ask('start-ble', '')
        driver.cmd.assert_not_called()
        driver.last_state_at = time.monotonic()-30
        with self.assertRaises(r.Stop):
            driver.tap({'resource-id': 'p35-start'})
        driver.cmd.assert_not_called()

    def test_no_update_cleanup_requires_real_target_completion_and_empty_idle(self):
        driver = self.driver()
        completed = state(self.fw, target=True, seq=5)
        idle = state(self.fw, target=True, idle=True, seq=6)
        driver.live = [completed]
        driver.tap = Mock()
        driver.wait = lambda check: (driver.live.append(idle), check())[1]
        self.assertEqual(driver.clear_at_target(completed), idle)
        driver.tap.assert_called_once_with({'resource-id': 'p35-check'})
        driver.idle_services.assert_called_once()
        for delta in ({'phase': 'idle'}, {'currentVersionCode': 30320}, {'freshConnection': False}):
            driver.tap.reset_mock()
            with self.subTest(delta=delta), self.assertRaises((RuntimeError, r.Stop)):
                driver.clear_at_target(dict(completed, **delta))
            driver.tap.assert_not_called()
        idle['protocol'] = 2
        with self.assertRaisesRegex(RuntimeError, 'NO_UPDATE'):
            driver.clear_at_target(completed)

    def test_restored_identity_without_idle_is_rejected(self):
        row = state(self.fw, idle=True)
        b.idle_base(row, self.fw)
        for delta in ({'phase': 'completed'}, {'protocol': 2}, {'session': 1}, {'durable': 1},
                      {'freshConnection': False}, {'packageVerified': True}, {'currentImageSha256': '0'*64}):
            with self.subTest(delta=delta), self.assertRaises((RuntimeError, r.Stop)):
                b.idle_base(dict(row, **delta), self.fw)

    def test_capacity_slots_and_time_boundaries(self):
        self.assertEqual([b.recording_slots(n) for n in (0, 31, 32)], [32, 1, 0])
        for value in (-1, 33, True):
            with self.assertRaises(RuntimeError):
                b.recording_slots(value)
        maximum = b.BUDGET['recorderBytes']-b.BUDGET['transferReserveBytes']-b.BUDGET['sealReserveBytes']
        self.assertTrue(b.has_reserve(maximum, 1801))
        self.assertFalse(b.has_reserve(maximum+1, 1801))
        self.assertFalse(b.has_reserve(0, 1800))
        for used, seconds in ((-1, 2000), (True, 2000), (0, float('inf')), (0, float('nan'))):
            with self.assertRaises(RuntimeError):
                b.has_reserve(used, seconds)

    def test_full_or_insufficient_archive_stops_before_old_file_retrieval(self):
        for count, minimum in ((32, 1), (31, 15)):
            driver = self.driver()
            driver.minimum_slots = minimum
            driver.capture_names = Mock(return_value=set(range(count)))
            with patch.object(b.obs.Observer, 'old_captures') as original, self.assertRaisesRegex(RuntimeError, 'archive slots'):
                driver.old_captures()
            original.assert_not_called()
            driver.cmd.assert_not_called()

    def test_last_recording_slot_remains_usable_after_initial_campaign_admission(self):
        campaign = h.fresh(self.out / 'all-slots')
        plan = dict(kind='patch', benchmark={}, phone=dict(limits=dict(total_seconds=5400)),
                    mcu=dict(package=self.fw['package']), firmware=self.fw, notify_cli={})
        def observed(current, folder, count, *, known_captures):
            index = len(known_captures)+1
            self.assertEqual(count, 2)
            with patch.object(b.obs.Observer, '__init__', return_value=None):
                driver = b.Observer(current, folder / 'phone', known_captures)
            self.assertEqual(driver.minimum_slots, 15 if index == 1 else 1)
            h.save(folder / 'cell-02/intent.json', dict(hostMonoNs=(14402 if index == 32 else index)*1_000_000_000))
            h.raw(folder / 'original.jsonl', b'synthetic campaign-controller original\n')
            value = dict(cells=[dict(beginObservedMonoNs=1_000_000_000)]*2, existingCaptures=index-1,
                         captureId='%032x' % index, original=h.record(folder / 'original.jsonl'))
            value['canonicalCaptures'] = dict(known_captures, **{value['captureId']: value['original']})
            h.save(folder / 'result.json', value)
            return value
        with patch.object(run, 'ble_block', side_effect=observed) as block:
            run.long_campaign(plan, campaign)
        self.assertEqual(block.call_count, 32)
        self.assertEqual(h.read_json(campaign / 'result.json')['attempts'], 64)

    def test_ci_triggers_cover_benchmark_execution_and_legacy_callers(self):
        workflow = (ROOT / '.github/workflows/acceptance-governance.yml').read_text(encoding='utf-8')
        paths = ('Tools/ota/p51-acceptance/benchmark.py', 'Tools/ota/p51-acceptance/fixture.py',
            'Tools/ota/p51-acceptance/run.py', 'Tools/ota/p51-acceptance/observation.py',
            'Tools/ota/p34-acceptance/live_phone.py', 'Tools/ota/p34-acceptance/selftest.py',
            'Tools/ota/p35-automation/smoke.py', 'Tools/ota/p35-automation/runner.py',
            'tests/ota/test_p51_benchmark_execution.py', 'tests/ota/test_p51_execution.py',
            'tests/ota/test_p51_clock.py', 'tests/ota/test_p51_public_proxy.mjs',
            'Tools/ota/p51-acceptance/public_proxy.py', 'Tools/ota/p51-acceptance/public/site/_worker.js')
        for event in ('push', 'pull_request'):
            section = re.search(r'(?ms)^  '+event+r':\n(.*?)(?=^  [a-z_]+:|\Z)', workflow)[1]
            patterns = re.findall(r'^      - "([^"]+)"$', section, re.M)
            for path in paths:
                matched = [pattern for pattern in patterns if fnmatch.fnmatchcase(path, pattern)]
                with self.subTest(event=event, path=path):
                    self.assertTrue(matched)
                    self.assertFalse(any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns if pattern not in matched))

    def test_ci_runs_existing_contained_entry_on_both_hosts(self):
        workflow = (ROOT / '.github/workflows/acceptance-governance.yml').read_text(encoding='utf-8')
        entry = h.host.load('p51_benchmark_selftest', ROOT / 'Tools/ota/p34-acceptance/selftest.py')
        self.assertEqual(entry.GROUPS['p51-benchmark'],
            ('test_p51_benchmark_execution.py', 'test_p51_execution.py', 'test_p51_clock.py'))
        for host, interpreter, shell in (('Linux', 'python3', 'bash'), ('Windows', 'python', 'cmd')):
            section = workflow.split('      - name: Test P51 benchmark execution adapters ('+host+')\n')[1].split('      - name:')[0]
            self.assertIn('shell: '+shell, section)
            self.assertIn(interpreter+' -I -S -B -X utf8 Tools/ota/p34-acceptance/selftest.py p51-benchmark', section)
            self.assertIn('working-directory: ${{ github.workspace }}', section)
            self.assertIn('--out ', section)
        self.assertIn('.cache/p51-benchmark-${{ github.run_id }}-${{ github.run_attempt }}/*.json', workflow)
        self.assertIn('.cache/p51-benchmark-${{ github.run_id }}-${{ github.run_attempt }}/*.log', workflow)

    def test_ci_prepares_real_fixture_dependencies_on_both_hosts(self):
        workflow = (ROOT/'.github/workflows/acceptance-governance.yml').read_text(encoding='utf-8')
        self.assertIn('os: [ubuntu-latest, windows-2022]', workflow)
        self.assertIn('-G "Visual Studio 17 2022" -A x64', workflow)
        for host in ('Linux', 'Windows'):
            preparation = workflow.split('      - name: Prepare P51 host packaging dependencies ('+host+')\n')[1].split('      - name:')[0]
            self.assertIn('pycryptodome==3.23.0', preparation)
            self.assertIn('--target ', preparation)
            self.assertIn('cmake -S .github/scripts/bsdiff -B .cache/p51-host-deps/bsdiff', preparation)
            self.assertIn('--target bsdiff', preparation)
            self.assertLess(workflow.index('Prepare P51 host packaging dependencies ('+host+')'),
                workflow.index('Test P51 benchmark execution adapters ('+host+')'))
            test = workflow.split('      - name: Test P51 benchmark execution adapters ('+host+')\n')[1].split('      - name:')[0]
            executable = 'bin/Release/bsdiff.exe' if host == 'Windows' else 'bin/bsdiff'
            self.assertIn('BSDIFF_EXE: ${{ github.workspace }}/.cache/p51-host-deps/bsdiff/'+executable, test)
        self.assertIn('P51_PYTHON_DEPS: ${{ github.workspace }}/.cache/p51-staging/python', workflow)
        self.assertIn('/fixtures/normal-*/prepare-*.stderr', workflow)

    def test_ci_entry_rejects_missing_explicit_dependencies_without_ambient_fallback(self):
        entry = h.host.load('p51_benchmark_missing_dependencies', ROOT/'Tools/ota/p34-acceptance/selftest.py')
        with patch.dict(os.environ, dict(P51_PYTHON_DEPS=str(self.out/'missing-deps'),
                BSDIFF_EXE=str(self.out/'missing-bsdiff.exe'))), \
                patch.object(sys, 'argv', ['selftest.py', 'p51-benchmark', '--out', str(self.out/'missing-entry')]), \
                patch.object(entry.host, 'run') as execute, self.assertRaisesRegex(RuntimeError, 'project-local pycryptodome'):
            entry.main()
        execute.assert_not_called()

    def test_phone_space_parse_is_strict(self):
        raw = b'Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/fuse 200 20 180 10% /storage/emulated\n'
        self.assertEqual(b.free_phone_bytes(raw), 180*1024)
        for bad in (b'', raw+b'extra\n', raw.replace(b' 180 ', b' unknown ')):
            with self.assertRaises(RuntimeError):
                b.free_phone_bytes(bad)

    def test_known_sealed_capture_reuses_local_bytes_only_after_phone_checks(self):
        driver = self.driver()
        raw, cid = b'public synthetic sealed-capture test double\n', 'e'*32
        original = self.out / 'canonical.jsonl'
        h.raw(original, raw)
        pin = h.record(original)
        driver.known_captures = {cid: pin}
        driver.cmd.side_effect = [str(len(raw)).encode()+b' file', pin['sha256'].encode()+b' file']
        destination = self.out / 'not-copied.jsonl'
        with patch.object(b.s, 'sealed_file', return_value={}) as seal:
            self.assertEqual(driver.original(cid, destination), raw)
        seal.assert_called_once_with(raw, cid)
        self.assertEqual(driver.cmd.call_count, 2)
        self.assertFalse(destination.exists())
        self.assertTrue(all(call.args[0][1] in ('wc', 'sha256sum') for call in driver.cmd.call_args_list))
        driver.cmd.side_effect = [str(len(raw)).encode(), b'0'*64]
        with patch.object(b.s, 'sealed_file', return_value={}), self.assertRaisesRegex(RuntimeError, 'archive changed'):
            driver.original(cid, destination)
        original.write_bytes(b'changed local')
        with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
            driver.original(cid, destination)

    def test_unknown_capture_uses_original_retrieval_owner(self):
        driver = self.driver()
        driver.known_captures = {}
        raw = sealed_capture('e'*32)
        h.raw(self.out / 'new.jsonl', raw)
        with patch.object(b.obs.Observer, 'original', return_value=raw) as original:
            self.assertEqual(driver.original('e'*32, self.out / 'new.jsonl'), raw)
        original.assert_called_once_with('e'*32, self.out / 'new.jsonl')
        self.assertEqual(driver.known_captures['e'*32], h.record(self.out / 'new.jsonl'))

    def test_initial_c0_original_is_promoted_and_never_downloaded_twice(self):
        driver = self.driver()
        driver.h, driver.capture_id, driver.known_captures = h, None, {}
        cid, raw = 'e'*32, sealed_capture('e'*32)
        digest = hashlib.sha256(raw).hexdigest().encode()
        driver.cmd.side_effect = [str(len(raw)).encode(), raw, digest, str(len(raw)).encode(), digest]
        first, second = self.out/'previous.jsonl', self.out/'not-duplicated.jsonl'
        self.assertEqual(driver.original(cid, first), raw)
        self.assertEqual(driver.original(cid, second), raw)
        self.assertFalse(second.exists())
        self.assertEqual(sum(call.args[0][:2] == ['exec-out', 'cat'] for call in driver.cmd.call_args_list), 1)
        self.assertEqual(driver.known_captures[cid], h.record(first))

    def test_c0_canonical_pin_survives_real_restart_bookkeeping(self):
        driver = self.driver()
        driver.h, driver.capture_id, driver.known_captures = h, None, {}
        driver.p.update(lifecycle=dict(restart_closed_recorder=True), device=dict(address=self.fw['device_address']))
        raw, cid = sealed_capture('e'*32), 'e'*32
        digest = hashlib.sha256(raw).hexdigest().encode()
        calls = []
        def cmd(args, **kwargs):
            calls.append(args)
            if args[:3] == ['shell', 'wc', '-c']:
                return str(len(raw)).encode()
            if args[:2] == ['shell', 'sha256sum']:
                return digest
            if args[:2] == ['exec-out', 'cat']:
                return raw
            if args[:3] == ['shell', 'ls', '-1']:
                return (cid+'.jsonl\n').encode()
            raise AssertionError(args)
        driver.cmd, driver.out = cmd, self.out
        driver.previous_captures, driver.capture_names = {}, Mock(return_value={cid})
        b.s.Smoke.old_captures(driver)
        driver.ui = Mock(return_value=('<hierarchy><node package="'+b.APP_ID+'" resource-id="p35-arm">'
            '<node package="'+b.APP_ID+'" content-desc="'+b.s.CLOSED_RECORDER+'"/></node></hierarchy>').encode())
        driver.restart_attempted, driver.pid = False, '123'
        driver.idle_recorder_ui, driver.stop_app_process, driver.navigate, driver.enter = Mock(), Mock(), Mock(), Mock()
        driver.launch = Mock(side_effect=lambda **kwargs: setattr(driver, 'pid', '456'))
        b.s.Smoke.prepare_recorder(driver)
        self.assertTrue(driver.restart_confirmed)
        driver.stop_app_process.assert_called_once_with('123', 'restart-stop')
        self.assertEqual(sum(args[:2] == ['exec-out', 'cat'] for args in calls), 1)
        self.assertFalse((self.out/'after-restart-captures').exists())

    def test_campaign_carries_all_c0_pins_and_respects_32_minus_c0(self):
        campaign = h.fresh(self.out/'c0-campaign')
        old = {}
        for index in range(17):
            cid = '%032x' % (index+100)
            path = self.out/(cid+'.jsonl')
            h.raw(path, sealed_capture(cid))
            old[cid] = h.record(path)
        plan = dict(kind='patch', benchmark={}, phone=dict(limits=dict(total_seconds=5400)),
                    mcu=dict(package=self.fw['package']))
        count = 0
        def observed(current, folder, max_cells, *, known_captures):
            nonlocal count
            count += 1
            self.assertEqual(max_cells, 2)
            if count > 1:
                self.assertTrue(all(known_captures.get(cid) == pin for cid, pin in old.items()))
            h.save(folder/'cell-02/intent.json', dict(hostMonoNs=(14402 if count == 15 else count)*1_000_000_000))
            cid = '%032x' % count
            h.raw(folder/'capture.jsonl', sealed_capture(cid))
            pin = h.record(folder/'capture.jsonl')
            result = dict(cells=[dict(beginObservedMonoNs=1_000_000_000)]*2,
                existingCaptures=17+count-1, captureId=cid, original=pin,
                canonicalCaptures={**old, **known_captures, cid: pin})
            h.save(folder/'result.json', result)
            return result
        with patch.object(run, 'ble_block', side_effect=observed):
            run.long_campaign(plan, campaign)
        self.assertEqual(count, 15)
        self.assertEqual(h.read_json(campaign/'result.json')['attempts'], 30)

    def test_mcu_readback_and_restore_share_absolute_deadline_with_cleanup_reserved(self):
        mcu = object.__new__(b.MCU)
        mcu.absolute_deadline = 500
        now, observed = [0], []
        def existing_execute(commands, reads, label, *, seconds, deadline):
            observed.append((label, deadline))
            now[0] += mcu.remaining(seconds, deadline)
            return {}, '', self.out
        with patch.object(b.obs.state_chain.m.MCU, 'execute', side_effect=existing_execute), \
                patch.object(b.time, 'monotonic', side_effect=lambda: now[0]):
            mcu.execute([], {}, 'delayed-readback')
            mcu.execute([], {}, 'delayed-restore-one')
            mcu.execute([], {}, 'delayed-restore-two')
            with self.assertRaisesRegex(RuntimeError, 'deadline'):
                mcu.execute([], {}, 'must-not-start')
        self.assertEqual(now[0], 500)
        self.assertEqual(observed, [('delayed-readback', 500), ('delayed-restore-one', 500), ('delayed-restore-two', 500)])

    def test_mcu_does_not_shorten_native_write_allowance_near_deadline(self):
        mcu = object.__new__(b.MCU)
        mcu.absolute_deadline = 1000
        with patch.object(b.obs.state_chain.m.MCU, 'execute') as native:
            with patch.object(b.time, 'monotonic', return_value=800), self.assertRaisesRegex(RuntimeError, 'mutation'):
                mcu.execute(['loadbin "synthetic.bin", 0x08010000'], {}, 'write')
            native.assert_not_called()
            with patch.object(b.time, 'monotonic', return_value=700):
                mcu.execute(['loadbin "synthetic.bin", 0x08010000'], {}, 'write')
            native.assert_called_once_with(['loadbin "synthetic.bin", 0x08010000'], {}, 'write', seconds=180, deadline=1000)

    def test_existing_restore_controller_keeps_one_deadline_across_delayed_stages(self):
        mcu = object.__new__(b.MCU)
        mcu.absolute_deadline, mcu.out = 1200, self.out
        mcu.bind = Mock(return_value=dict(table=dict(g_restore_control=(0x20000000, 640))))
        mcu.install = lambda *_: mcu.execute(['loadbin "synthetic.bin", 0x08010000'], {}, 'install')
        mcu.restore_state = lambda phase: mcu.execute([], {}, 'restore-state-%d' % phase)[0]
        mcu.wait_boot = lambda role: mcu.execute([], {}, 'wait-'+role)
        mcu.inspect = lambda role, label: mcu.execute([], {}, label)[0]
        observed, now = [], [0]
        def execute(commands, reads, label, *, seconds, deadline):
            observed.append((label, deadline))
            now[0] += 90
            return {key: b'\xff'*size for key, size in reads.items()}, '', self.out
        with patch.object(b.obs.state_chain.m.MCU, 'execute', side_effect=execute), \
                patch.object(b.time, 'monotonic', side_effect=lambda: now[0]):
            mcu.restore()
        self.assertEqual([label for label, _ in observed], ['install', 'restore-state-1', 'restore-arm',
            'restore-state-3', 'ordinary-boot-rollback', 'wait-base', 'rollback-full-readback', 'rollback-staging-zero'])
        self.assertEqual({end for _, end in observed}, {1200})
        self.assertEqual(now[0], 720)
        self.assertTrue(h.read_json(self.out/'restore-result.json')['journal_erased'])

    def test_unsealed_unknown_original_is_preserved_but_never_cached(self):
        driver = self.driver()
        driver.h, driver.capture_id, driver.known_captures = h, None, {}
        raw, cid = b'unsealed original', 'd'*32
        driver.cmd.side_effect = [str(len(raw)).encode(), raw, hashlib.sha256(raw).hexdigest().encode()]
        path = self.out/'failed-original.jsonl'
        with self.assertRaises(r.Stop):
            driver.original(cid, path)
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(driver.known_captures, {})

    def test_non_apk_rejected_before_build_claims_or_device_calls(self):
        apk = self.out/'not-an-apk.bin'
        h.raw(apk, b'not an APK')
        pin = h.record(apk)
        plan = dict(apk=pin, firmware=self.fw,
            phone=dict(app=dict(id=b.APP_ID, version_code=98, release=True, sha256=pin['sha256'])))
        with self.assertRaisesRegex(RuntimeError, 'actual APK'):
            b.apk_binding(plan)

    def apk_claim(self, *, native=None):
        # Complete synthetic relationships exercise admission, not Android
        # authenticity. The dedicated real APK is separately inspected natively.
        native = native if native is not None else b'\x7fELF'+self.fw['latest_url'].encode()+b'\0'+b.LINK_PROFILE.encode()
        with io.BytesIO() as stream:
            with zipfile.ZipFile(stream, 'w') as archive:
                archive.writestr('AndroidManifest.xml', b'\x03\x00\x08\x00synthetic manifest')
                for abi in ('arm64-v8a', 'armeabi-v7a'):
                    archive.writestr('lib/'+abi+'/libapp.so', native)
            apk_bytes = stream.getvalue()
        h.raw(self.out/'app.apk', apk_bytes)
        apk = h.record(self.out/'app.apk')
        app = dict(id=b.APP_ID, version_code=100, release=True, sha256=apk['sha256'])
        with io.BytesIO() as stream:
            with zipfile.ZipFile(stream, 'w') as archive:
                archive.writestr('ble-monitor-android.apk', apk_bytes)
            h.raw(self.out/'apk-artifact.zip', stream.getvalue())
        artifact_pin = h.record(self.out/'apk-artifact.zip')
        workflow = dict(head_sha='a'*40, head_branch='dev/flutter/synthetic',
            repository=dict(id=1, full_name='Eitan-S-23/E-Track'),
            head_repository=dict(id=1, full_name='Eitan-S-23/E-Track'), status='completed',
            conclusion='success', event='workflow_dispatch', path='.github/workflows/build.yml', id=123, run_attempt=1)
        h.save(self.out/'apk-run.json', workflow)
        jobs = [dict(name=name, run_id=123, run_attempt=1, status='completed', conclusion=conclusion)
            for name, conclusion in (('Build Android APK', 'success'), ('Build Windows EXE', 'success'),
                ('Create GitHub Release', 'skipped'), ('Deploy GitHub Pages', 'skipped'))]
        h.save(self.out/'apk-jobs.json', dict(total_count=len(jobs), jobs=jobs))
        h.save(self.out/'dispatch.json', dict(method='POST', route='/actions/workflows/build.yml/dispatches',
            body=dict(ref=workflow['head_branch'], inputs=dict(publish_release='false', replace_existing_release='false',
                firmware_latest_url=self.fw['latest_url'], release_ota_link_profile=b.LINK_PROFILE,
                release_application_id_suffix='.p51benchmark'))))
        h.raw(self.out/'workflow.log', ('OTA build intent: '+b.LINK_PROFILE+'\n'
            'Release application id suffix enabled: .p51benchmark\n').encode())
        tools = {}
        for name in ('java', 'aapt', 'signer'):
            tools[name] = h.raw(self.out/('synthetic-'+name), ('not executable: '+name).encode())
        def receipt(name, argv, text):
            stdout = h.raw(self.out/(name+'.stdout'), text.encode())
            stderr = h.raw(self.out/(name+'.stderr'), b'')
            path = self.out/(name+'.closed.json')
            h.save(path, dict(argv=argv, exit_code=0, exit_status='exited', stopped_while_running=False,
                cleanup_complete=True, cleanup_errors=[], stdout=stdout, stderr=stderr))
            return h.record(path)
        apk_path = str(h.pinned(apk))
        badging = receipt('badging', [str(h.pinned(tools['aapt'])), 'dump', 'badging', apk_path],
            "package: name='"+b.APP_ID+"' versionCode='100' versionName='1.0.72'\n")
        signature = receipt('signature', [str(h.pinned(tools['java'])), '-jar', str(h.pinned(tools['signer'])),
            'verify', '--verbose', '--print-certs', apk_path],
            'Signer #1 certificate SHA-256 digest: '+b.SIGNER+'\nNumber of signers: 1\n')
        h.save(self.out/'inspection.json', dict(apk=apk, tools=tools, badging=badging, signature=signature))
        build = dict(schema='p51-benchmark-apk-v1', apk=apk, app=app, latestUrl=self.fw['latest_url'],
            publishRelease=False, source='a'*40, linkProfile=b.LINK_PROFILE,
            workflowRun=h.record(self.out/'apk-run.json'), workflowJobs=h.record(self.out/'apk-jobs.json'),
            archive=artifact_pin, artifact=dict(id=456, name='android-apk', workflow_run=dict(id=123, head_sha='a'*40),
                digest='sha256:'+artifact_pin['sha256'], size_in_bytes=artifact_pin['bytes']),
            dispatch=h.record(self.out/'dispatch.json'), workflowLog=h.record(self.out/'workflow.log'),
            inspection=h.record(self.out/'inspection.json'))
        h.save(self.out/'app-build.json', build)
        plan = dict(apk=apk, phone=dict(app=app), firmware=self.fw,
            benchmark=dict(app_build=h.record(self.out/'app-build.json')))
        return plan, build, {name: pin['sha256'] for name, pin in tools.items()}

    def test_apk_original_relationships_pass_and_reject_individual_mismatches(self):
        plan, original, tool_hashes = self.apk_claim()
        with patch.dict(b.INSPECTION_TOOLS, tool_hashes, clear=True):
            self.assertEqual(b.apk_binding(plan), original)
            mutations = (('workflowRun', 'repository', dict(id=1, full_name='foreign/repo')),
                ('workflowRun', 'run_attempt', 2), ('workflowRun', 'head_sha', 'f'*40),
                ('dispatch', 'body', dict(ref='other-branch', inputs={})),
                ('workflowJobs', 'jobs', []), ('inspection', 'badging', {}))
            for index, (pin_name, field, value) in enumerate(mutations):
                changed = h.read_json(h.pinned(original[pin_name]))
                changed[field] = value
                changed_path = self.out/('negative-%d.json' % index)
                h.save(changed_path, changed)
                build = dict(original, **{pin_name: h.record(changed_path)})
                path = self.out/('build-negative-%d.json' % index)
                h.save(path, build)
                test_plan = dict(plan, benchmark=dict(app_build=h.record(path)))
                with self.subTest(pin=pin_name, field=field), self.assertRaises((RuntimeError, KeyError)):
                    b.apk_binding(test_plan)

    def test_binary_apk_endpoint_cannot_be_replaced_by_a_build_claim(self):
        plan, _, _ = self.apk_claim(native=b'\x7fELFhttps://wrong.invalid/'+b.LINK_PROFILE.encode())
        with self.assertRaisesRegex(RuntimeError, 'compiled APK endpoint/profile'):
            b.apk_binding(plan)

    def test_binary_apk_profile_cannot_be_replaced_by_a_build_claim(self):
        plan, _, _ = self.apk_claim(native=b'\x7fELF'+self.fw['latest_url'].encode()+b'\0baseline-v1')
        with self.assertRaisesRegex(RuntimeError, 'compiled APK endpoint/profile'):
            b.apk_binding(plan)

    def test_apk_native_inspection_failure_and_wrong_file_are_rejected(self):
        plan, original, tool_hashes = self.apk_claim()
        inspection = h.read_json(h.pinned(original['inspection']))
        receipt = h.read_json(h.pinned(inspection['signature']))
        for index, delta in enumerate((dict(exit_code=1), dict(cleanup_complete=False),
                dict(argv=receipt['argv'][:-1]+['wrong.apk']))):
            receipt_path = self.out/('signature-negative-%d.json' % index)
            h.save(receipt_path, dict(receipt, **delta))
            inspection_path = self.out/('inspection-negative-%d.json' % index)
            h.save(inspection_path, dict(inspection, signature=h.record(receipt_path)))
            build_path = self.out/('inspect-build-negative-%d.json' % index)
            h.save(build_path, dict(original, inspection=h.record(inspection_path)))
            with patch.dict(b.INSPECTION_TOOLS, tool_hashes, clear=True), self.assertRaises(RuntimeError):
                b.apk_binding(dict(plan, benchmark=dict(app_build=h.record(build_path))))

    def test_native_originals_reject_missing_logs_failed_process_and_source_drift(self):
        names = ('Tools/ota/p34-acceptance/reference_host.c', 'Libraries/OTA/ota_patch.c',
            'Libraries/OTA/ota_keys.c', 'boot/src/boot_crc32.c', 'boot/src/boot_sha256.c', 'boot/src/boot_fw_header.c',
            'bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c', 'bsdiff_lzma_AES128-main/bspatch/AES128_CTR/aes_core.c',
            'Libraries/OTA/ota_package.c')
        cwd, area = '/synthetic/source', '/synthetic/source/.cache/p51-candidate'
        compiler = ['gcc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror', '-DP51_ALL_ASSETS=1',
            '-DOTA_PATCH_COALESCE_WRITES=1', '-DCONFIG_OTA_APP_CRC32_NIBBLE=1', '-include', area+'/private/key.h']
        compiler += [cwd+'/'+name for name in names]+['-o', area+'/private/decoder']
        observed = dict(result='ok', passed=True, byte_identical=True)
        verification = dict(native=dict(sources={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in names}, checks=[dict(case='positive', observation=observed)]))
        files = {}
        for name in ('compile', 'positive'):
            prefix = 'evidence/native/'+name
            argv = compiler if name == 'compile' else [area+'/private/decoder', area+'/private/positive.etu',
                area+'/inputs/base.bin', area+'/prepared/app-final.bin', 'ok']
            files[prefix+'.process.json'] = json.dumps(dict(stage=name, argv=argv, cwd=cwd, exitCode=0,
                signal=None, timeout=False, treeCleanupComplete=True, interrupted=None, cleanupErrors=[])).encode()
            files[prefix+'.stderr.txt'] = b''
            files[prefix+'.stdout.txt'] = b'' if name == 'compile' else json.dumps(observed).encode()
            if name == 'positive':
                files[prefix+'.observation.json'] = json.dumps(observed).encode()
        b.native_originals(verification, files)
        for key in ('evidence/native/positive.stdout.txt', 'evidence/native/compile.process.json'):
            changed = dict(files)
            del changed[key]
            with self.assertRaises(KeyError):
                b.native_originals(verification, changed)
        for delta in (dict(exitCode=1), dict(treeCleanupComplete=False), dict(signal=9)):
            changed = dict(files)
            key = 'evidence/native/positive.process.json'
            changed[key] = json.dumps(dict(json.loads(files[key]), **delta)).encode()
            with self.assertRaises(RuntimeError):
                b.native_originals(verification, changed)
        changed = copy.deepcopy(verification)
        changed['native']['sources'][names[0]] = '0'*64
        with self.assertRaisesRegex(RuntimeError, 'source drift'):
            b.native_originals(changed, files)

    def archive_claim(self):
        archive = self.out/'archive.zip'
        with io.BytesIO() as stream:
            with zipfile.ZipFile(stream, 'w') as output:
                output.writestr('synthetic.txt', b'original synthetic payload')
            h.raw(archive, stream.getvalue())
        pin = h.record(archive)
        run = dict(head_sha='a'*40, repository=dict(id=1, full_name='Eitan-S-23/E-Track'),
            head_repository=dict(id=1, full_name='Eitan-S-23/E-Track'), status='completed',
            conclusion='success', event='workflow_dispatch', path='.github/workflows/build.yml', id=123, run_attempt=1)
        h.save(self.out/'run.json', run)
        artifact = dict(id=456, name='android-apk', workflow_run=dict(id=123, head_sha='a'*40),
            digest='sha256:'+pin['sha256'], size_in_bytes=pin['bytes'])
        return dict(source='a'*40, workflowRun=h.record(self.out/'run.json'), artifact=artifact, archive=pin), run

    def test_workflow_archive_requires_exact_repository_source_run_and_bytes(self):
        delivery, original = self.archive_claim()
        run, files = b.workflow_archive(delivery, 'build.yml', 'android-apk')
        self.assertEqual(files, {'synthetic.txt': b'original synthetic payload'})
        self.assertEqual(run, original)
        for field, value in (('repository', dict(id=1, full_name='foreign/repo')), ('head_sha', 'f'*40),
            ('run_attempt', 0), ('id', 124), ('conclusion', 'failure'), ('event', 'push')):
            with self.subTest(field=field), patch.object(h, 'read_json', return_value=dict(original, **{field: value})), \
                    self.assertRaises(RuntimeError):
                b.workflow_archive(delivery, 'build.yml', 'android-apk')
        for field, value in (('name', 'wrong'), ('digest', 'sha256:'+'0'*64), ('size_in_bytes', 1),
            ('workflow_run', dict(id=999, head_sha='a'*40))):
            with self.subTest(field=field), self.assertRaises(RuntimeError):
                b.workflow_archive(dict(delivery, artifact=dict(delivery['artifact'], **{field: value})), 'build.yml', 'android-apk')

    def test_package_cannot_admit_json_claims_without_original_delivery(self):
        with self.assertRaises(KeyError):
            b.package_binding(dict(benchmark={}, mcu={}))

    def test_reserve_failure_cannot_construct_mcu_or_start_first_transfer(self):
        plan = dict(kind='patch', benchmark={}, mcu=dict(package=dict(bytes=1048576)))
        driver = Mock(capture_id=None, capture_resolved=True)
        driver.next_transfer.return_value = False
        with patch.object(b, 'Observer', return_value=driver), patch.object(b, 'MCU') as mcu, \
                self.assertRaisesRegex(RuntimeError, 'budget exhausted'):
            run.ble_block(plan, self.out, 2)
        mcu.assert_not_called()
        driver.ready_package.assert_not_called()
        driver.close.assert_called_once()

    def test_more_than_two_benchmark_cells_rejected_before_phone_creation(self):
        with patch.object(b, 'Observer') as phone, self.assertRaises(RuntimeError):
            run.ble_block(dict(kind='patch', benchmark={}, mcu=dict(package=dict(bytes=1048576))), self.out, 3)
        phone.assert_not_called()

    def test_benchmark_channel_uses_fixture_without_public_channel_mutation(self):
        with patch.object(b, 'check_fixture') as check, patch.object(run, 'h'):
            with run.channel(dict(benchmark={}), self.out, True):
                pass
        check.assert_called_once()

    def test_manual_observer_still_refuses_ui_automation(self):
        with self.assertRaises(RuntimeError):
            b.obs.Observer.tap(None)

    def test_two_blocks_save_success_then_clear_restore_idle_and_reuse_archive(self):
        trace, created = [], []
        plan = dict(kind='patch', benchmark={}, mcu=dict(package=self.fw['package']),
                    firmware=self.fw, notify_cli={}, _campaign_deadline=time.monotonic()+2700)
        def phone_factory(plan, out, known):
            phone = Mock(out=out, capture_id=('%032x' % (len(created)+1)), capture_resolved=True,
                         pid='123', previous_captures=dict(known or {}))
            phone.known_captures = dict(known or {})
            phone.recording_deadline = time.monotonic()+3000
            phone.live, phone.sequence = [], 0
            phone.next_transfer.return_value = True
            def emit(*, target=False, idle=False):
                phone.sequence += 1
                row = state(self.fw, target=target, idle=idle, seq=phone.sequence)
                phone.live.append(row)
                return row
            def identity(*args, **kwargs):
                trace.append('identity-base-idle')
                return emit(idle=True)
            phone.fresh_identity.side_effect = identity
            phone.ready_package.side_effect = lambda fw: emit()
            def wait(check):
                begin = emit()
                begin.update(event='beginAck', phase='transferring')
                emit(target=True)
                return check()
            phone.wait.side_effect = wait
            def clear(completed):
                files = list(out.parent.glob('cell-*/result.json'))
                self.assertTrue(any(h.read_json(path)['finalInfo'] == completed for path in files))
                trace.append('clear-target-after-saved-success')
            phone.clear_at_target.side_effect = clear
            def finish(**kwargs):
                h.raw(out / 'app-capture.jsonl', b'synthetic block original for controller test\n')
                phone.known_captures[phone.capture_id] = h.record(out / 'app-capture.jsonl')
                h.save(out / 'observation.json', dict(synthetic=True))
                trace.append('seal-idle')
                return dict(groups=[dict(label='upgrade')]*2)
            phone.finish.side_effect = finish
            created.append(phone)
            return phone
        def mcu_factory(plan, out, *, deadline):
            self.assertLess(deadline, created[-1].recording_deadline)
            self.assertEqual(deadline, outer_deadline-180)
            mcu = Mock(out=out)
            mcu.inspect.return_value = dict(storage=dict(journal=dict(expected_begin_durable=0,
                matches_reference=True, durable=1048576, committed_target=30321)))
            def restore():
                trace.append('verified-restore')
                h.save(out / 'restore-result.json', dict(synthetic=True))
            mcu.restore.side_effect = restore
            return mcu
        known = {}
        outer_deadline = plan['_campaign_deadline']
        with patch.object(b, 'Observer', side_effect=phone_factory), patch.object(b, 'MCU', side_effect=mcu_factory):
            for index in (1, 2):
                folder = h.fresh(self.out / ('block-%02d' % index))
                result = run.ble_block(plan, folder, 2, known_captures=known)
                self.assertEqual(len(result['cells']), 2)
                self.assertEqual(result['existingCaptures'], index-1)
                known[result['captureId']] = result['original']
        self.assertEqual(len(known), 2)
        self.assertEqual(trace, ['identity-base-idle', 'clear-target-after-saved-success', 'verified-restore',
            'identity-base-idle', 'identity-base-idle', 'clear-target-after-saved-success', 'verified-restore',
            'identity-base-idle', 'seal-idle']*2)
        self.assertTrue(all(phone.close.call_count == 1 for phone in created))

    def test_fixture_owner_starts_existing_network_once_and_closes_on_stop(self):
        out = self.out / 'owner'
        network_out = out / 'network'
        network = Mock(out=network_out)
        def start(**kwargs):
            h.save(network_out / 'ready.json', dict(origin='https://fixture.trycloudflare.com'))
            h.save(out / 'stop.json', dict(sourceSha256=h.record(Path(fixture.__file__))['sha256'], pid=os.getpid()))
            return 'https://fixture.trycloudflare.com'
        def close():
            h.save(network_out / 'closed.json', dict(cleanup_complete=True))
        network.start.side_effect, network.close.side_effect = start, close
        plan = dict(schema='p51-benchmark-fixture-v1', kind='patch', benchmark=dict(purpose='fixed-load-benchmark'),
            phone=dict(app=dict(id=b.APP_ID)), mcu=dict(package={}))
        selected = dict(tools=dict(cloudflared={}))
        with patch.object(b, 'package_binding'), patch.object(b, 'network_plan', return_value=selected), \
                patch.object(h, 'pinned'), patch.object(b.live_phone, 'reference_binding'), \
                patch.object(b.live_phone, 'Network', return_value=network), patch.object(fixture.signal, 'signal'):
            fixture.serve(plan, out, 25200)
        network.start.assert_called_once()
        network.close.assert_called_once()
        self.assertEqual(h.read_json(out / 'result.json')['outcome'], 'FIXTURE_STOPPED_BY_OWNER')

    def test_fixture_startup_failure_closes_existing_owner_without_restart(self):
        out = self.out / 'failed-owner'
        network = Mock(out=out / 'network')
        network.start.side_effect = RuntimeError('synthetic startup failure')
        plan = dict(schema='p51-benchmark-fixture-v1', kind='patch', benchmark=dict(purpose='fixed-load-benchmark'),
            phone=dict(app=dict(id=b.APP_ID)), mcu=dict(package={}))
        with patch.object(b, 'package_binding'), patch.object(b, 'network_plan', return_value=dict(tools=dict(cloudflared={}))), \
                patch.object(h, 'pinned'), patch.object(b.live_phone, 'reference_binding'), \
                patch.object(b.live_phone, 'Network', return_value=network), patch.object(fixture.signal, 'signal'), \
                self.assertRaisesRegex(RuntimeError, 'synthetic startup'):
            fixture.serve(plan, out, 25200)
        network.start.assert_called_once()
        network.close.assert_called_once()
        self.assertTrue((out / 'failed.json').is_file())
        self.assertFalse((out / 'result.json').exists())

    def test_fixture_lifetime_is_checked_before_any_https_request(self):
        owner = self.out / 'short-fixture'
        ready = owner / 'network/ready.json'
        h.save(ready, dict(origin='https://fixture.trycloudflare.com'))
        pin = h.record(ready)
        h.save(owner / 'status.json', dict(ready=pin, monotonicNs=time.monotonic_ns(),
            deadlineMonotonicNs=time.monotonic_ns()+100_000_000_000))
        with patch.object(h, 'command') as command, self.assertRaisesRegex(RuntimeError, 'lifetime'):
            b.check_fixture(dict(benchmark=dict(fixture_ready=pin)), self.out / 'fixture-check')
        command.assert_not_called()

    def proxy_claim(self):
        proxy = b.public_proxy
        upstream = 'https://fixture.trycloudflare.com'
        selected = self.fixture()
        cli, owner = self.out / 'proxy-cli', self.out / 'proxy-owner'
        config = cli / 'wrangler.jsonc'
        worker = cli / 'site/_worker.js'
        h.save(config, proxy.deployment_config(upstream))
        h.raw(worker, (proxy.PUBLIC / 'site/_worker.js').read_bytes())
        h.save(owner / 'service-config.json', b.live_phone.service_config(selected, proxy.ORIGIN))
        expected = dict(origin=proxy.ORIGIN, upstream_origin=upstream, package=selected['package'],
            service_config=h.record(owner / 'service-config.json'))
        h.save(owner / 'upstream-ready.json', dict(expected, upstream=upstream,
            source=h.record(Path(fixture.__file__))))
        tools = {}
        for name in ('node', 'wrangler', 'git'):
            h.raw(cli / name, b'synthetic native tool input; never executed\n')
            tools[name] = h.record(cli / name)
        source, ident = 'b'*40, '11111111-1111-1111-1111-111111111111'
        source_commands = {}
        for key, name in proxy.SOURCE_PATHS.items():
            label = cli / ('source-'+key)
            h.raw(label.with_suffix('.stdout'), (ROOT/name).read_bytes().replace(b'\r\n', b'\n'))
            h.raw(label.with_suffix('.stderr'), b'')
            h.save(label.with_suffix('.closed.json'), dict(argv=[str(h.pinned(tools['git'])),
                '--no-optional-locks', 'show', source+':'+name], exit_code=0,
                exit_status='exited', stopped_while_running=False, cleanup_complete=True,
                cleanup_errors=[], stdout=h.record(label.with_suffix('.stdout')),
                stderr=h.record(label.with_suffix('.stderr'))))
            source_commands[key] = h.record(label.with_suffix('.closed.json'))
        url = 'https://11111111.' + proxy.PROJECT + '.pages.dev'
        h.raw(cli / 'deploy.stdout', ('Deployment complete: ' + url).encode())
        h.raw(cli / 'deploy.stderr', b'')
        h.save(cli / 'deploy.closed.json', dict(argv=[str(h.pinned(tools[key])) for key in ('node', 'wrangler')] +
            ['pages', 'deploy', str(worker.parent), '--project-name', proxy.PROJECT, '--branch', 'main',
             '--commit-hash', source, '--commit-dirty=false', '--no-bundle', '--upload-source-maps=false',
             '--cwd', str(cli)], exit_code=0, exit_status='exited', stopped_while_running=False,
            cleanup_complete=True, cleanup_errors=[], stdout=h.record(cli / 'deploy.stdout'),
            stderr=h.record(cli / 'deploy.stderr')))
        native = dict(type='pages-deploy-detailed', deployment_id=ident, pages_project=proxy.PROJECT,
            url=url, environment='production', deployment_trigger=dict(metadata=dict(commit_hash=source)))
        h.raw(cli / 'output.jsonl', (json.dumps(native)+'\n').encode())
        variables = dict(P51_UPSTREAM_ORIGIN=dict(type='plain_text', value=upstream))
        canonical = dict(id=ident, project_name=proxy.PROJECT, environment='production', url=url,
            latest_stage=dict(status='success'), deployment_trigger=dict(metadata=dict(commit_hash=source, commit_dirty=False)),
            env_vars=variables, compatibility_date='2026-11-08')
        project = dict(name=proxy.PROJECT, subdomain=proxy.PROJECT+'.pages.dev', production_branch='main',
            canonical_deployment=canonical, deployment_configs=dict(production=dict(
                env_vars=variables, compatibility_date='2026-11-08')))
        h.save(cli / 'project.json', dict(success=True, result=project))
        h.save(cli / 'project-http.json', dict(method='GET', status=200, body=h.record(cli / 'project.json'),
            url='https://api.cloudflare.com/client/v4/accounts/'+'a'*32+'/pages/projects/'+proxy.PROJECT))
        value = dict(schema='p51-pages-proxy-v1', project=proxy.PROJECT, origin=proxy.ORIGIN, upstream=upstream,
            configuration=h.record(config), worker=h.record(worker), upstream_ready=h.record(owner/'upstream-ready.json'),
            source=source, tools=tools, source_commands=source_commands,
            deploy_command=h.record(cli/'deploy.closed.json'),
            deploy_output=h.record(cli/'output.jsonl'), project_response=h.record(cli/'project.json'),
            project_http=h.record(cli/'project-http.json'), account='a'*32)
        h.save(owner / 'public-proxy.json', value)
        return h.record(owner / 'public-proxy.json'), expected, value

    def test_fixed_proxy_requires_matching_native_deploy_api_and_fixture_originals(self):
        pin, expected, value = self.proxy_claim()
        self.assertEqual(b.public_proxy.validate_publication(pin, expected), value)
        for index, (key, changed) in enumerate((('project', 'normal-site'),
                ('origin', 'https://other.pages.dev'), ('upstream', 'https://other.trycloudflare.com'),
                ('source', 'c'*40), ('account', 'd'*32))):
            candidate = dict(value, **{key: changed})
            path = self.out / ('claim-%d.json' % index)
            h.save(path, candidate)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                b.public_proxy.validate_publication(h.record(path), expected)

    def test_fixed_proxy_rejects_failed_native_receipt_or_unrelated_output(self):
        _, expected, value = self.proxy_claim()
        for index, delta in enumerate((dict(exit_code=1), dict(cleanup_complete=False),
                dict(stopped_while_running=True), dict(argv=['not-the-deployment']))):
            command = dict(h.read_json(h.pinned(value['deploy_command'])), **delta)
            receipt = self.out / ('bad-receipt-%d.json' % index)
            claim = self.out / ('bad-claim-%d.json' % index)
            h.save(receipt, command)
            h.save(claim, dict(value, deploy_command=h.record(receipt)))
            with self.assertRaisesRegex(RuntimeError, 'native Pages deployment'):
                b.public_proxy.validate_publication(h.record(claim), expected)
        h.raw(self.out/'unrelated-output.jsonl', b'{"type":"pages-deploy-detailed","deployment_id":"other"}\n')
        h.save(self.out/'unrelated.json', dict(value, deploy_output=h.record(self.out/'unrelated-output.jsonl')))
        with self.assertRaisesRegex(RuntimeError, 'identity mismatch'):
            b.public_proxy.validate_publication(h.record(self.out/'unrelated.json'), expected)

    def test_fixed_proxy_requires_both_exact_successful_git_source_commands(self):
        _, expected, value = self.proxy_claim()
        for key in b.public_proxy.SOURCE_PATHS:
            original = h.read_json(h.pinned(value['source_commands'][key]))
            deltas = (dict(exit_code=1), dict(exit_status='unknown'), dict(cleanup_complete=False),
                dict(cleanup_errors=[dict(step='stdout_close')]), dict(stopped_while_running=True),
                dict(argv=original['argv'][:-1]+['c'*40+':'+b.public_proxy.SOURCE_PATHS[key]]),
                dict(argv=original['argv'][:-1]+[value['source']+':unrelated-file']))
            for index, delta in enumerate(deltas):
                receipt = self.out / ('bad-git-%s-%d.json' % (key, index))
                claim = self.out / ('bad-git-claim-%s-%d.json' % (key, index))
                h.save(receipt, dict(original, **delta))
                h.save(claim, dict(value, source_commands=dict(value['source_commands'], **{key: h.record(receipt)})))
                with self.subTest(key=key, delta=delta), self.assertRaisesRegex(RuntimeError, 'native Git source'):
                    b.public_proxy.validate_publication(h.record(claim), expected)
        h.save(self.out/'missing-git.json', dict(value, source_commands={}))
        with self.assertRaises(KeyError):
            b.public_proxy.validate_publication(h.record(self.out/'missing-git.json'), expected)

    def test_fixed_proxy_compares_git_blob_bytes_not_commit_labels(self):
        _, expected, value = self.proxy_claim()
        for key in b.public_proxy.SOURCE_PATHS:
            original = h.read_json(h.pinned(value['source_commands'][key]))
            for variant, raw in (('changed', b'not the committed source\n'),
                    ('crlf', h.pinned(original['stdout']).read_bytes().replace(b'\n', b'\r\n'))):
                output = self.out / ('git-%s-%s.stdout' % (key, variant))
                receipt = self.out / ('git-%s-%s.closed.json' % (key, variant))
                claim = self.out / ('git-%s-%s-claim.json' % (key, variant))
                h.raw(output, raw)
                h.save(receipt, dict(original, stdout=h.record(output)))
                candidate = dict(value, source_commands=dict(value['source_commands'], **{key: h.record(receipt)}))
                h.save(claim, candidate)
                with self.subTest(key=key, variant=variant):
                    if variant == 'changed':
                        with self.assertRaisesRegex(RuntimeError, 'Git blob content'):
                            b.public_proxy.validate_publication(h.record(claim), expected)
                    else:
                        self.assertEqual(b.public_proxy.validate_publication(h.record(claim), expected), candidate)

    def test_fixed_proxy_resolves_native_tool_aliases_without_changing_receipts(self):
        _, expected, value = self.proxy_claim()
        for index, (key, position) in enumerate((('node', 0), ('wrangler', 1), ('git', 0))):
            pin = value['tools'][key]
            original_tool = h.pinned(pin)
            directory = h.fresh(original_tool.parent/('alias-%d'%index))
            alias = str(directory) + '/../' + original_tool.name
            receipt_pin = value['source_commands']['worker'] if key == 'git' else value['deploy_command']
            original = h.read_json(h.pinned(receipt_pin))
            command = copy.deepcopy(original)
            command['argv'][position] = alias
            receipt = self.out/('alias-%d.closed.json'%index)
            claim = self.out/('alias-%d-claim.json'%index)
            h.save(receipt, command)
            candidate = copy.deepcopy(value)
            if key == 'git':
                candidate['source_commands']['worker'] = h.record(receipt)
            else:
                candidate['deploy_command'] = h.record(receipt)
            h.save(claim, candidate)
            before = receipt.read_bytes()
            self.assertEqual(b.public_proxy.validate_publication(h.record(claim), expected), candidate)
            self.assertEqual(receipt.read_bytes(), before)
            self.assertEqual(h.read_json(receipt)['argv'][position], alias)

    def test_fixed_proxy_rejects_other_native_files_and_relative_tool_arguments(self):
        _, expected, value = self.proxy_claim()
        receipt = h.read_json(h.pinned(value['deploy_command']))
        other = self.out/'different-node'
        h.raw(other, h.pinned(value['tools']['node']).read_bytes())
        for index, argument in enumerate((str(other), 'node', str(other.parent/'missing-node'))):
            command = copy.deepcopy(receipt)
            command['argv'][0] = argument
            path = self.out/('wrong-tool-%d.closed.json'%index)
            claim = self.out/('wrong-tool-%d-claim.json'%index)
            h.save(path, command)
            h.save(claim, dict(value, deploy_command=h.record(path)))
            with self.subTest(argument=argument), self.assertRaises(RuntimeError):
                b.public_proxy.validate_publication(h.record(claim), expected)

    def test_fixed_proxy_generated_configuration_allows_only_upstream_substitution(self):
        _, expected, value = self.proxy_claim()
        original = h.read_json(h.pinned(value['configuration']))
        changed = dict(original, compatibility_date='2026-11-07')
        config = self.out/'changed/wrangler.jsonc'
        h.save(config, changed)
        h.save(self.out/'changed-config-claim.json', dict(value, configuration=h.record(config)))
        with self.assertRaisesRegex(RuntimeError, 'configuration drift'):
            b.public_proxy.validate_publication(h.record(self.out/'changed-config-claim.json'), expected)

    def test_fixed_proxy_publication_first_visible_bytes_are_complete(self):
        pin, expected, value = self.proxy_claim()
        destination = self.out/'published/public-proxy.json'
        pending = destination.with_suffix('.json.tmp')
        replace = h.host.io.replace_file
        def partial_dump(item, stream, **kwargs):
            stream.write('{')
            stream.flush()
            self.assertEqual(pending.read_bytes(), b'{')
            self.assertFalse(destination.exists())
            stream.write(json.dumps(item, **kwargs)[1:])
        def expose(root, source, target):
            self.assertEqual(source, pending)
            self.assertEqual(target, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(h.read_json(source), value)
            return replace(root, source, target)
        with patch.object(h.host.io.json, 'dump', side_effect=partial_dump), \
                patch.object(h.host.io, 'replace_file', side_effect=expose) as replacement:
            published = b.public_proxy.publish(pin, expected, destination)
        replacement.assert_called_once()
        self.assertEqual(published, h.record(destination))
        self.assertEqual(destination.read_bytes(), h.pinned(pin).read_bytes())
        self.assertFalse(pending.exists())

    def test_fixed_proxy_publication_preserves_existing_or_partial_pending_files(self):
        pin, expected, _ = self.proxy_claim()
        for name, is_pending in (('existing', False), ('incomplete', True)):
            destination = self.out/name/'public-proxy.json'
            pending = destination.with_suffix('.json.tmp')
            old = pending if is_pending else destination
            h.raw(old, b'{"unfinished":')
            with patch.object(h.host.io, 'write_json') as writer, self.assertRaisesRegex(RuntimeError, 'prior/uncertain'):
                b.public_proxy.publish(pin, expected, destination)
            writer.assert_not_called()
            self.assertEqual(old.read_bytes(), b'{"unfinished":')
            self.assertFalse((destination if is_pending else pending).exists())

    def test_fixed_proxy_publication_validation_or_write_failure_never_exposes_partial_json(self):
        pin, expected, _ = self.proxy_claim()
        rejected = self.out/'rejected/public-proxy.json'
        with self.assertRaises(RuntimeError):
            b.public_proxy.publish(pin, dict(expected, origin='https://foreign.pages.dev'), rejected)
        self.assertFalse(rejected.exists())
        self.assertFalse(rejected.with_suffix('.json.tmp').exists())
        destination = self.out/'interrupted/public-proxy.json'
        def interrupted_dump(item, stream, **kwargs):
            stream.write('{')
            raise OSError('synthetic interrupted write')
        with patch.object(h.host.io.json, 'dump', side_effect=interrupted_dump), \
                self.assertRaisesRegex(OSError, 'interrupted write'):
            b.public_proxy.publish(pin, expected, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(destination.with_suffix('.json.tmp').read_bytes(), b'{')

    def test_fixed_proxy_rejects_redirected_service_urls_and_handwritten_pass(self):
        _, expected, value = self.proxy_claim()
        h.save(self.out/'pass-only.json', dict(outcome='PASS'))
        with self.assertRaises(RuntimeError):
            b.public_proxy.validate_publication(h.record(self.out/'pass-only.json'), expected)
        config = h.read_json(h.pinned(expected['service_config']))
        config['publicBaseUrl'] = 'https://fixture.trycloudflare.com'
        h.save(self.out/'wrong-service.json', config)
        upstream = h.read_json(h.pinned(value['upstream_ready']))
        upstream['service_config'] = h.record(self.out/'wrong-service.json')
        h.save(self.out/'wrong-upstream.json', upstream)
        h.save(self.out/'wrong-publication.json', dict(value, upstream_ready=h.record(self.out/'wrong-upstream.json')))
        with self.assertRaisesRegex(RuntimeError, 'download URLs'):
            b.public_proxy.validate_publication(h.record(self.out/'wrong-publication.json'),
                dict(expected, service_config=upstream['service_config']))

    def test_fixed_proxy_rejects_changed_remote_upstream_or_data_bindings(self):
        _, expected, value = self.proxy_claim()
        for index, delta in enumerate((dict(env_vars={}), dict(services={'DB': {}}))):
            response = h.read_json(h.pinned(value['project_response']))
            response['result']['deployment_configs']['production'].update(delta)
            path = self.out/('remote-%d.json' % index)
            http = h.read_json(h.pinned(value['project_http']))
            h.save(path, response)
            http['body'] = h.record(path)
            http_path = self.out/('remote-http-%d.json' % index)
            claim = self.out/('remote-claim-%d.json' % index)
            h.save(http_path, http)
            h.save(claim, dict(value, project_response=h.record(path), project_http=h.record(http_path)))
            with self.assertRaisesRegex(RuntimeError, 'observed upstream'):
                b.public_proxy.validate_publication(h.record(claim), expected)

    def test_fixed_fixture_publication_is_checked_before_network_readiness(self):
        out = self.out / 'fixed-owner'
        network = Mock(out=out/'network')
        def start(**kwargs):
            self.assertEqual(kwargs['public_origin'], b.public_proxy.ORIGIN)
            h.save(network.out/'service-config.json', dict(publicBaseUrl=kwargs['public_origin']))
            h.save(network.out/'public-proxy.json', dict(synthetic=True))
            publication = kwargs['publish']('https://fixture.trycloudflare.com',
                h.record(network.out/'service-config.json'), kwargs['deadline'])
            self.assertEqual(publication, h.record(network.out/'public-proxy.json'))
            check.assert_called_once()
            h.save(network.out/'ready.json', dict(origin=kwargs['public_origin'], public_proxy=publication))
            h.save(out/'stop.json', dict(sourceSha256=h.record(Path(fixture.__file__))['sha256'], pid=os.getpid()))
            return kwargs['public_origin']
        network.start.side_effect = start
        network.close.side_effect = lambda: h.save(network.out/'closed.json', dict(cleanup_complete=True))
        plan = dict(schema='p51-benchmark-fixture-v1', kind='patch', benchmark=dict(purpose='fixed-load-benchmark'),
            phone=dict(app=dict(id=b.APP_ID)), mcu=dict(package={}),
            public_proxy=dict(project=b.public_proxy.PROJECT, origin=b.public_proxy.ORIGIN))
        with patch.object(b, 'package_binding'), patch.object(b, 'network_plan', return_value=dict(tools=dict(cloudflared={}))), \
                patch.object(h, 'pinned'), patch.object(b.live_phone, 'reference_binding'), \
                patch.object(b.live_phone, 'Network', return_value=network), patch.object(fixture.signal, 'signal'), \
                patch.object(b.public_proxy, 'validate_publication') as check:
            fixture.serve(plan, out, 25200)
        self.assertTrue((network.out/'upstream-ready.json').is_file())
        network.start.assert_called_once()
        network.close.assert_called_once()

    def fixture(self):
        images = {}
        for name, code in (('base', 30320), ('target', 30321)):
            raw = bytearray(0x500)
            struct.pack_into('<I', raw, 0x408, code)
            path = self.out / (name+'.bin')
            h.raw(path, raw)
            images[name] = dict(image=h.record(path))
        payload = bytes(1048576-64)
        header = bytearray(64)
        header[:4] = b'ETU1'
        struct.pack_into('<HHII', header, 4, 64, 7, 1, 1)
        struct.pack_into('<IIIIHBB', header, 32, len(payload), zlib.crc32(payload), 30321, 30320, 1, 1, 1)
        header[52:60] = bytes.fromhex(images['base']['image']['sha256'])[:8]
        struct.pack_into('<I', header, 60, zlib.crc32(header[:60]))
        packet = self.out / 'synthetic-outer-container.etu'
        h.raw(packet, header+payload)
        return dict(images=images, package=h.record(packet), reference_service=dict(baseVersion=30320,
            targetVersion=30321, appVersion=100, releaseId='p51-benchmark-30320-30321', purpose='P51 fixed-load benchmark only'))

    def test_existing_service_selects_truthful_patch_and_target_no_update(self):
        plan = self.fixture()
        query = b.live_phone.service_query(plan)
        cfg = b.live_phone.service_config(plan, 'https://fixture.trycloudflare.com')
        service = b.live_phone.service.V2ServiceState(cfg, str(ROOT))
        pairs = lambda q: [(k, str(v)) for k, v in q.items()]
        status, _, raw = service.handle_latest(pairs(query))
        value = json.loads(raw)
        self.assertEqual(status, 200)
        self.assertEqual(value['asset']['kind'], 'patch')
        self.assertEqual(value['asset']['sizeBytes'], 1048576)
        url = urlsplit(value['asset']['downloadUrl'])
        status, _, raw = service.handle_download(parse_qsl(url.query), None, None)
        self.assertEqual(status, 200)
        self.assertEqual(raw, h.pinned(plan['package']).read_bytes())
        status, _, raw = service.handle_latest(pairs(dict(query, currentVersionCode=30321,
            currentImageSha=plan['images']['target']['image']['sha256'])))
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(raw)['updateAvailable'])
        with self.assertRaises(b.live_phone.service.ServiceError):
            service.handle_latest(pairs(dict(query, currentImageSha='0'*64)))

    def test_explicit_service_versions_and_scope_cannot_drift(self):
        plan = self.fixture()
        binding = plan['reference_service']
        for delta in ({'baseVersion': 30318}, {'targetVersion': 30319}, {'appVersion': True},
            {'releaseId': 'normal'}, {'purpose': 'normal-upgrade'}):
            with self.subTest(delta=delta), self.assertRaises(RuntimeError):
                b.live_phone.service_config(dict(plan, reference_service=dict(binding, **delta)), 'https://fixture.trycloudflare.com')
        self.assertEqual(b.live_phone.reference_binding({})['baseVersion'], 30286)
        self.assertEqual(b.live_phone.reference_binding({})['appVersion'], 86)


if __name__ == '__main__':
    unittest.main()
