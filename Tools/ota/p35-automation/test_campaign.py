"""Offline integration of the real preparation, campaign and shared cleanup."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import runner as r
import smoke as s
import test_runner as campaign_fixture
import test_smoke as native_fixture


def plan():
    p = campaign_fixture.plan()
    native = native_fixture.plan()
    p.update(phone=native['phone'], app=native['app'])
    p['firmware']['device_address'] = native['device']['address']
    p['firmware']['protocol'] = 2
    p['ui'] = dict(arm=s.ARM, stop=s.STOP, check={'resource-id': 'p35-check'},
        download={'resource-id': 'p35-download'}, start={'resource-id': 'p35-start'},
        resume={'resource-id': 'p35-start'}, navigate=[], reconnect=[s.QUERY])
    p['limits'] = dict(total_seconds=120, stage_seconds=10, event_seconds=5, disconnect_seconds=1)
    p['preparation'] = dict(display_name='', command_seconds=5, cleanup_seconds=20, restart_closed_recorder=False)
    for case in p['cases']:
        case['bitmap'] = 'any'
    return p


class Device(native_fixture.SyntheticDevice):
    def __init__(self, out, host, fault=None):
        super().__init__(out, host, fault=fault)
        self.pid = None
        self.radio_on = True
        self.pending = []
        self.completed = self.no_update_seen = False
        self.upgrade_starts = self.arms = self.stops = 0
        self.resume_index = 0
        self.workers = []
        self.log_tag = 'M'
        self.startup_logging = False

    def push(self, sample):
        self.seq += 1
        row = dict(sample, seq=self.seq, captureId=self.cid,
            monoUs=int((self.now - self.started) * 1000000), deviceAddress=plan()['firmware']['device_address'])
        self.rows.append(row)
        self.append((r.PREFIX + json.dumps(row) + '\n').encode())

    def transfer(self, **changes):
        return campaign_fixture.state(protocol=2, bitmap=None, phase='transferring', **changes)

    def emit(self, event):
        row = native_fixture.state(event=event)
        if self.startup_logging and not self.upgrade_starts:
            row.update(targetVersionCode=0, targetImageSha256=None, releaseId=None,
                packageBytes=0, packageSha256=None, packageVerified=False, latestUrl=None)
        if self.fault == 'identity-mismatch':
            row['currentImageSha256'] = 'f' * 64
        self.push(row)

    def sleep(self, seconds):
        self.now += seconds
        if self.pending and seconds >= .02:
            self.push(self.pending.pop(0))

    def tree(self):
        if self.page != 'firmware':
            return super().tree()
        items = [native_fixture.node(s.FIRMWARE),
            native_fixture.node('recording' if self.active else 'off', identifier='p35-stop' if self.active else 'p35-arm'),
            native_fixture.node(identifier='p35-reconnect', bounds='[130,20][230,80]'),
            native_fixture.node(identifier='p35-check', bounds='[240,20][340,80]'),
            native_fixture.node(identifier='p35-download', bounds='[350,20][450,80]'),
            native_fixture.node(identifier='p35-start', bounds='[460,20][560,80]')]
        if self.no_update_seen:
            items.append(native_fixture.node('\u6682\u65e0\u53ef\u7528\u66f4\u65b0'))
        return native_fixture.xml(*items)

    def command(self, args):
        if args == ['shell', 'getprop', 'ro.build.fingerprint']:
            self.calls.append(args)
            return r.RADIO_FINGERPRINT.encode()
        if args == ['shell', 'sha256sum', r.RADIO_FRAMEWORK]:
            self.calls.append(args)
            return (r.RADIO_FRAMEWORK_SHA256 + '  ' + r.RADIO_FRAMEWORK).encode()
        if args == list(r.RADIO_BINDER):
            self.calls.append(args)
            return ("Result: Parcel(00000000 %08x   '........')\n" % (12 if self.radio_on else 10)).encode()
        if args == ['shell', 'getprop', 'log.tag']:
            self.calls.append(args)
            return (self.log_tag + '\n').encode()
        if args[:3] == ['shell', 'setprop', 'log.tag']:
            self.calls.append(args)
            self.log_tag = args[-1]
            self.startup_logging = True
            if self.log_tag == 'M' and self.active:
                self.pending.extend([dict(self.rows[-1], event='heartbeat')] * 2)
            return b''
        if args == ['shell', 'dumpsys', 'bluetooth_manager']:
            self.calls.append(args)
            if self.fault in {'empty-manager', 'adapter-restore-transitional'}:
                return b''
            return ('state: ' + ('ON' if self.radio_on else 'OFF') + '\n').encode()
        if args == list(r.RADIO_ADAPTER):
            self.calls.append(args)
            value = 'ON' if self.radio_on else 'OFF'
            if self.fault == 'adapter-restore-transitional' and self.radio_on and self.resume_index == 0 and self.upgrade_starts:
                value = 'TURNING_ON'
            # Synthetic OFF/turning only; actual phone evidence qualifies ON.
            return ('    AdapterProperties\n      State: ' + value + '\n'
                    '    Profile\n      State: OFF\n').encode()
        if args[:3] == ['shell', 'cmd', 'bluetooth_manager']:
            self.calls.append(args)
            if self.fault == 'restore-failure' and args[-1] == 'enable':
                raise r.Stop('ENV_BLOCKED', 'one uncertain restore attempt')
            self.radio_on = args[-1] == 'enable'
            row = dict(self.rows[-1], phase='failed', linkConnected=False, freshConnection=False)
            self.push(row)
            return b''
        if self.page == 'firmware' and args[:3] == ['shell', 'input', 'tap']:
            point = args[-2:]
            if point == ['60', '50']:
                if not self.active:
                    self.arms += 1
                else:
                    self.stops += 1
                return super().command(args)
            self.calls.append(args)
            if self.fault == 'campaign-tap-timeout':
                raise r.Stop('TIMEOUT', 'uncertain business tap')
            if point == ['180', '50']:
                self.push(dict(self.rows[-1], phase='failed' if self.resume_index else 'idle',
                    event='identity', freshConnection=True, linkConnected=True))
            elif point == ['290', '50']:
                if self.completed:
                    self.push(dict(self.rows[-1], phase='checkingUpdate', event='state'))
                    self.push(native_fixture.state(phase='failed' if self.fault == 'no-update-failure' else 'idle',
                        currentVersionCode=30294, currentImageSha256='d'*64,
                        latestUrl=plan()['firmware']['latest_url'], targetVersionCode=0, targetImageSha256=None,
                        releaseId=None, packageSha256=None, packageBytes=0, packageVerified=False))
                    self.no_update_seen = True
                else:
                    self.push(native_fixture.state(phase='checkingUpdate'))
                    self.push(campaign_fixture.state(protocol=None, bitmap=None, packageVerified=False))
            elif point == ['400', '50']:
                self.push(campaign_fixture.state(protocol=None, bitmap=None, phase='readyToInstall'))
            elif point == ['510', '50']:
                if not self.upgrade_starts:
                    self.upgrade_starts = 1
                    self.push(self.transfer(event='beginAck'))
                    self.push(self.transfer(durable=4096 if self.fault == 'missed-window' else 0))
                else:
                    case = plan()['cases'][self.resume_index]
                    off = case['durable_min']
                    session = self.resume_index + 2
                    self.push(self.transfer(event='beginAck', durable=off, session=session))
                    self.push(self.transfer(event='data', durable=off, session=session, sendOffset=off))
                    self.push(self.transfer(durable=off + 4096, session=session))
                    self.resume_index += 1
                    if self.resume_index == 10:
                        self.completed = True
                        self.push(campaign_fixture.state(protocol=2, bitmap=None,
                            phase='failed' if self.fault=='unverified-reboot' else 'completed', event='identity',
                            currentVersionCode=30293 if self.fault=='unverified-reboot' else 30294,
                            currentImageSha256=('c' if self.fault=='unverified-reboot' else 'd')*64, durable=1048576))
                    else:
                        self.pending.append(self.transfer(durable=plan()['cases'][self.resume_index]['durable_min']))
            else:
                raise AssertionError('unexpected semantic action')
            return b''
        return super().command(args)

    def process(self, *args):
        self.workers.append(args[1])
        return super().process(*args)


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = r.load_host()
        cls.area = cls.host.fresh(r.ROOT / '.cache/p35-campaign-30294-20261030/cases' / ('suite-' + uuid.uuid4().hex))
        sys.path.insert(0, str(r.ROOT / 'Tools/ota/p34-acceptance'))
        import live_phone
        cls.live_phone = live_phone

    def run_case(self, fault=None, locked=False, startup_logging=False, info_baseline=False, radio_getter=False, single=False):
        host = self.host
        case = host.fresh(self.area / ('case-' + uuid.uuid4().hex))
        out = case / 'evidence'
        device = Device(out, host, fault)
        real_phone = self.live_phone.Phone
        class Phone:
            def __init__(self, p, usb, seconds):
                self.out = host.fresh(usb)
                self.env = host.environment(usb)
                self.port = 5093
                self.serial, self.pkg = 'SYNTHETIC', plan()['app']['id']
                self.plan, self.base = p, ['SYNTHETIC_ADB']
                self.server = None
                self.operation_deadline = None
            def cmd(self, args, **kwargs):
                return device.command(args)
            def installed(self):
                return real_phone.installed(self)
            def close(self):
                if self.server:
                    self.server.close('synthetic shared closure')
        config = case / 'plan.json'
        configuration = plan()
        if single:
            configuration.update(test_profile='single-upgrade', cases=[], allow_bluetooth_toggle=False)
        if radio_getter:
            configuration['preparation']['radio_state_reader'] = 'vivo-pd2312-sdk33-getState-v1'
        if startup_logging:
            configuration['preparation']['startup_log_tag'] = dict(before='M', during='V', seconds=300)
            if info_baseline:
                configuration['preparation']['startup_log_tag']['allow_info_baseline'] = True
                device.log_tag = 'I'
        host.save(config, configuration)
        lock = case / '.cache/p34-live-device.lock'
        if locked:
            host.save(lock, dict(pid=os.getpid(), out=str(out)))
            original = lock.read_bytes()
        cwd = Path.cwd()
        try:
            os.chdir(case)
            with patch.object(r, 'ROOT', case), patch.object(s, 'ROOT', case), patch.object(host, 'ROOT', case), \
                 patch.object(r, 'load_host', lambda: host), patch.object(self.live_phone, 'Phone', Phone), \
                 patch.object(host, 'Process', device.process), patch.object(host, 'pinned', lambda item: Path('synthetic-read-only')), \
                 patch.object(host, 'listening', lambda port: bool(device.server and device.server.alive())), \
                 patch.object(r.time, 'monotonic', device.mono), patch.object(r.time, 'sleep', device.sleep), \
                 patch.object(s.Smoke, 'record_smoke', side_effect=AssertionError('must not run a preliminary smoke')):
                code = r.main(['run', '--plan', str(config), '--out', str(out), '--execute'] +
                              (['--single-upgrade'] if single else []))
        finally:
            os.chdir(cwd)
        self.assertFalse(device.server and device.server.alive())
        self.assertFalse(device.logger and device.logger.alive())
        self.assertFalse(any(c[0] in ('install', 'uninstall') or 'clear' in c for c in device.calls))
        if locked:
            self.assertEqual(lock.read_bytes(), original)
        return code, host.read_json(out/'result.json'), device, out, lock

    def test_one_command_one_capture_ten_recoveries_no_update_and_shared_cleanup(self):
        code, result, device, out, lock = self.run_case()
        self.assertEqual(code, 0)
        self.assertEqual(result['recovered'], 10)
        self.assertEqual(result['noUpdate']['outcome'], 'NO_UPDATE')
        self.assertEqual([x['outcome'] for x in result['caseResults']], ['PASS'] * 10)
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 1, 1))
        self.assertEqual(device.workers, ['adb-server', 'logcat'])
        self.assertEqual(sum(c[:3] == ['shell','cmd','bluetooth_manager'] and c[-1] == 'disable' for c in device.calls), 10)
        self.assertTrue(result['cleanup']['complete'])
        self.assertFalse(lock.exists())
        self.assertEqual((out/'app-capture.jsonl').read_bytes(), device.raw)
        self.assertTrue(device.no_update_seen)

    def test_opt_in_startup_logging_restored_before_single_complete_campaign(self):
        code, result, device, out, lock = self.run_case(startup_logging=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['recovered'], 10)
        self.assertEqual(device.log_tag, 'M')
        writes = [c for c in device.calls if c[:3] == ['shell', 'setprop', 'log.tag']]
        self.assertEqual([c[-1] for c in writes], ['V', 'M'])
        restore_index = device.calls.index(writes[1])
        check_index = next(i for i, c in enumerate(device.calls) if c == ['shell', 'input', 'tap', '290', '50'])
        self.assertLess(restore_index, check_index)
        self.assertFalse(lock.exists())
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 1, 1))

    def test_navigation_failure_never_arms_or_starts_ota(self):
        code, result, device, out, lock = self.run_case('list-missing')
        self.assertEqual((device.arms, device.upgrade_starts), (0, 0))
        self.assertEqual(code, 2)
        self.assertTrue(result['cleanup']['complete'])
        self.assertFalse(lock.exists())

    def test_info_baseline_completes_real_caller_without_property_writes(self):
        code, result, device, out, lock = self.run_case(startup_logging=True, info_baseline=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['recovered'], 10)
        self.assertEqual(result['noUpdate']['outcome'], 'NO_UPDATE')
        self.assertFalse(any(c[:3] == ['shell', 'setprop', 'log.tag'] for c in device.calls))
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 1, 1))
        self.assertEqual((out / 'app-capture.jsonl').read_bytes(), device.raw)
        self.assertFalse(lock.exists())

    def test_bound_getter_completes_ten_recoveries_without_adapter_dump_dependency(self):
        code, result, device, out, lock = self.run_case(radio_getter=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['recovered'], 10)
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 1, 1))
        self.assertFalse(any(c == list(r.RADIO_ADAPTER) or c == list(r.RADIO_MANAGER) for c in device.calls))
        self.assertEqual(device.calls.count(['shell', 'sha256sum', r.RADIO_FRAMEWORK]), 1)
        self.assertEqual((out / 'app-capture.jsonl').read_bytes(), device.raw)
        self.assertFalse(lock.exists())

    def test_empty_manager_adapter_reader_completes_one_synthetic_group(self):
        code, result, device, out, lock = self.run_case('empty-manager')
        self.assertEqual(code, 0)
        self.assertEqual(result['recovered'], 10)
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 1, 1))
        self.assertEqual(sum(args == list(r.RADIO_MANAGER) for args in device.calls), 1)
        self.assertGreater(sum(args == list(r.RADIO_ADAPTER) for args in device.calls), 20)
        self.assertEqual(device.workers, ['adb-server', 'logcat'])
        self.assertTrue(result['cleanup']['complete'])
        self.assertEqual((out/'app-capture.jsonl').read_bytes(), device.raw)
        self.assertFalse(lock.exists())

    def test_adapter_transition_restore_failure_keeps_original_and_never_replays(self):
        code, result, device, out, lock = self.run_case('adapter-restore-transitional')
        self.assertEqual(code, 2)
        self.assertEqual(device.upgrade_starts, 1)
        self.assertEqual(sum(args[:3] == ['shell', 'cmd', 'bluetooth_manager'] and args[-1] == 'enable'
                             for args in device.calls), 1)
        self.assertTrue(result['cleanup']['radioErrors'])
        self.assertTrue(lock.exists())
        self.assertTrue((out/'logcat.stdout').read_bytes())

    def test_identity_mismatch_never_starts_ota_and_preserves_recording(self):
        code, result, device, out, lock = self.run_case('identity-mismatch')
        self.assertEqual(code, 2)
        self.assertEqual(device.upgrade_starts, 0)
        self.assertTrue(lock.exists())
        self.assertTrue((out/'logcat.stdout').read_bytes())

    def test_uncertain_navigation_is_not_replayed_and_keeps_owner(self):
        code, result, device, out, lock = self.run_case('tap-timeout')
        self.assertEqual(code, 2)
        self.assertEqual(sum(c[:3] == ['shell','input','tap'] for c in device.calls), 1)
        self.assertEqual(device.upgrade_starts, 0)
        self.assertTrue(lock.exists())

    def test_existing_lock_prevents_all_device_operations(self):
        _, result, device, _, _ = self.run_case(locked=True)
        self.assertEqual(device.calls, [])
        self.assertEqual(device.workers, [])

    def test_missed_window_keeps_raw_attempt_and_never_restarts_group(self):
        code, result, device, out, lock = self.run_case('missed-window')
        self.assertEqual(code, 2)
        self.assertEqual(device.upgrade_starts, 1)
        self.assertEqual(device.arms, 1)
        self.assertEqual(device.stops, 0)
        self.assertTrue(lock.exists())
        self.assertTrue((out/'logcat.stdout').read_bytes())
        self.assertEqual(result['caseResults'][0]['outcome'], 'FAIL')

    def test_failed_post_upgrade_query_seals_original_without_repeating_upgrade(self):
        code, result, device, out, lock = self.run_case('no-update-failure')
        self.assertEqual(code, 2)
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 1, 1))
        self.assertEqual(result['recovered'], 10)
        self.assertEqual([x['outcome'] for x in result['caseResults']], ['RECOVERY_OBSERVED'] * 10)
        self.assertTrue(result['cleanup']['complete'])
        self.assertFalse(lock.exists())
        self.assertEqual((out/'app-capture.jsonl').read_bytes(), device.raw)

    def test_radio_restore_failure_is_not_replayed_and_keeps_evidence(self):
        code, result, device, out, lock = self.run_case('restore-failure')
        self.assertEqual(code, 2)
        self.assertEqual(sum(c[:3] == ['shell','cmd','bluetooth_manager'] and c[-1] == 'enable' for c in device.calls), 1)
        self.assertEqual(device.upgrade_starts, 1)
        self.assertTrue(lock.exists())
        self.assertTrue((out/'logcat.stdout').read_bytes())
        self.assertTrue(result['cleanup']['radioErrors'])

    def test_remote_digest_failure_preserves_raw_and_never_repeats_stop(self):
        code, result, device, out, lock = self.run_case('remote-hash')
        self.assertEqual(code, 2)
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 1, 1))
        self.assertTrue(lock.exists())
        self.assertEqual((out/'app-capture.jsonl').read_bytes(), device.raw)

    def test_unknown_post_transfer_identity_never_stops_app_or_replays_upgrade(self):
        code, result, device, out, lock = self.run_case('unverified-reboot')
        self.assertEqual(code, 2)
        self.assertEqual((device.arms, device.stops, device.upgrade_starts), (1, 0, 1))
        self.assertEqual(result['recovered'], 10)
        self.assertTrue(lock.exists())
        self.assertTrue((out/'logcat.stdout').read_bytes())
        self.assertEqual((out/'failed-original-prefix.jsonl').read_bytes(), device.raw)
        self.assertFalse(result['cleanup']['ownedAppClosed'])


if __name__ == '__main__':
    unittest.main()
