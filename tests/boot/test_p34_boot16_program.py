import copy
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
sys.path.insert(0, str(ROOT / 'tests/boot'))
from recovery_confirm import boot16_program as p, boot16_owner as owner
from test_p34_boot16 import BootSDK, ORIGINAL, PLAN, Dap
from test_p34_boot16_entry import SDK, IMAGE, MAP, Clock
from test_p34_boot16_probe import Native, BinaryBuffer, record, run as probe
from test_p34_boot16_archive import ArchiveTests
from recovery_confirm import boot16_reconcile as audit


class Combined(SDK):
    def __init__(self, clock, boot=ORIGINAL):
        super().__init__(clock)
        self.flash = BootSDK(clock, boot+IMAGE)
        self.memory.update({a: v for a, v in self.flash.memory.items()
                            if a not in (p.DHCSR, p.PAUSE)})
        self.flash.memory = self.memory
        self.memory[probe.entry.USB_CONNECTION] = 0x104
        self.core[17] = 0x20057fa0
        h = probe.entry.health
        self.memory.update({h.SD: 1, h.DIAG: 1, h.FAULT: 0, h.TICK: 0})
        self.memory.update({h.HEALTH+4*i: v for i, v in enumerate((30000, 30, 1000, 0, 0, 0, 0, 1, 1))})

    def JLINKARM_CORESIGHT_ReadAPDPReg(self, index, ap, output):
        if (index, ap) == (3, 1) and p.boot16.START <= self.tar < p.APP+p.APP_BYTES:
            self.flash.tar = self.tar
            result = self.flash.JLINKARM_CORESIGHT_ReadAPDPReg(index, ap, output)
            self.tar = self.flash.tar
            return result
        return super().JLINKARM_CORESIGHT_ReadAPDPReg(index, ap, output)

    def JLINKARM_CORESIGHT_WriteAPDPReg(self, index, ap, value):
        if (index, ap) == (3, 1) and (p.boot16.START <= self.tar < p.APP+p.APP_BYTES or
                                     p.flash.FLASH <= self.tar < p.flash.FLASH+0x100):
            self.flash.tar = self.tar
            self.writes.append((self.tar, value))
            result = self.flash.JLINKARM_CORESIGHT_WriteAPDPReg(index, ap, value)
            self.tar = self.flash.tar
            return result
        return super().JLINKARM_CORESIGHT_WriteAPDPReg(index, ap, value)


class MemoryArchive:
    def __init__(self, fail=None):
        self.data, self.saved, self.fail = {}, None, fail

    def __call__(self, name, offset, raw):
        if self.fail == name: raise OSError('injected archive failure')
        data = self.data.setdefault(name, bytearray())
        if len(data) != offset: raise ValueError('out-of-order archive')
        data.extend(raw)

    def verify(self, label, boot, image):
        if self.data[label+'-boot'] != boot or self.data[label+'-app'] != image:
            raise ValueError('archive mismatch')
        return dict(verified=True)

    def checkpoint(self, body):
        if self.fail == 'checkpoint': raise OSError('checkpoint unavailable')
        if body.boot_may_have_changed: raise ValueError('late checkpoint')
        self.verify('before', body.preimage, body.image)
        self.saved = dict(before=copy.deepcopy(body.control.before),
                          context=copy.deepcopy(body.control.context_before))


class FastLogs:
    def __init__(self, clock):
        self.clock = clock
        self.gate = SimpleNamespace(paths=list(range(p.LOG_COUNT)), index=1, boundary=True)
        self.rows, self.seals = [], []
        self.failure = None

    def emit(self, event, **fields): self.rows.append(dict(event=event, **fields))
    def target_allowed(self): return True
    def verify_head(self): pass
    def switch(self, *, read_allowed, expected_stores):
        if self.failure == self.gate.index: raise ValueError('injected seal failure')
        actual = [(r['address'], r['value']) for r in self.rows if r['event'] == 'recovery-word-write-returned']
        if actual != list(expected_stores): raise ValueError('independent store plan differs')
        for row in self.rows:
            if row['event'] == 'recovery-word-read' and not read_allowed(row['address']):
                raise ValueError('unexpected read scope')
        self.rows.clear()
        self.seals.append(tuple(expected_stores))
        self.gate.index += 1
        return dict(target_writes=len(actual), native_close=0, log_file_closed=1)


def fast_body(*, retained=None, boot=ORIGINAL, archive_fail=None):
    clock = Clock()
    sdk = Combined(clock, boot)
    logs, archive = FastLogs(clock), MemoryArchive(archive_fail)
    if retained:
        sdk.memory[p.DHCSR] = 0x30003
        sdk.memory[p.PAUSE] = retained['before']['pause'] | 0x1000
        sdk.memory[p.REGS['dfsr']] = retained['before']['dfsr'] | 2
    body = p.Body(Dap(sdk), logs, lambda: 6000-clock.value, archive, IMAGE, MAP, PLAN,
        direction='restore' if retained is not None else 'activate', retained=retained,
        checkpoint=archive.checkpoint, clock=clock, sleep=clock.sleep,
        guard=lambda f, *a, **k: f(*a))
    logs.dap = body.dap
    return body, sdk, logs, archive, clock


class Tests(unittest.TestCase):
    def test_body_complete_capture_sector_oracle_and_same_context_exit(self):
        body, sdk, logs, archive, clock = fast_body()
        original_sleep = clock.sleep
        def sleep(seconds):
            original_sleep(seconds)
            if not sdk.memory[p.DHCSR] & 0x20000:
                h = probe.entry.health
                values = (30000, 30, 1000, 0, int(clock.value*100), int(clock.value*100), 0, 1, 1)
                sdk.memory.update({h.TICK: int(clock.value*1000), h.SD: 1, h.DIAG: 1, h.FAULT: 0})
                sdk.memory.update({h.HEALTH+4*i: v for i, v in enumerate(values)})
        body.sleep = sleep
        result = body.run()
        self.assertEqual(result['result'], 'BOOT16_READY_FOR_NATIVE_CLOSE')
        self.assertEqual(bytes(sdk.flash.flash), PLAN.activated+IMAGE)
        self.assertEqual(len(body.sectors), 8)
        self.assertEqual(logs.gate.index, p.LOG_COUNT-1)
        self.assertEqual(archive.saved['context']['msp'], 0x20057fa0)
        self.assertEqual(body.results['health']['samples'], 31)
        self.assertEqual([v for a, v in sdk.writes if a == p.DHCSR], [0xa05f0001])
        expected = [x for i in range(8) for x in p.boot16.stores(PLAN, ORIGINAL, i, 'activate')]
        self.assertEqual(sdk.flash.write_log, expected)
        calls = sdk.calls
        with self.assertRaises(ValueError): body.run()
        self.assertEqual(sdk.calls, calls)

    def test_preimage_suffix_app_or_archive_failure_blocks_all_flash_writes(self):
        for failure in ('prefix', 'suffix', 'app', 'before-app', 'checkpoint'):
            body, sdk, _, _, _ = fast_body(archive_fail=failure)
            if failure in ('prefix', 'suffix', 'app'):
                sdk.flash.flash[{'prefix': 0, 'suffix': 20000, 'app': 65536+20000}[failure]] ^= 1
            with self.assertRaises((ValueError, OSError)): body.run()
            self.assertFalse(sdk.flash.write_log, failure)
            self.assertFalse(body.release_started)

    def test_interrupted_program_and_postcapture_never_cleanup_or_release(self):
        for failure in ('delivered', 'busy', 'after-boot', 'audit'):
            body, sdk, logs, archive, _ = fast_body(archive_fail=failure)
            if failure in ('delivered', 'busy'): sdk.flash.fault = failure
            if failure == 'audit': logs.failure = 24
            with self.assertRaises((ValueError, OSError)): body.run()
            self.assertTrue(body.boot_may_have_changed)
            self.assertFalse(body.release_started)
            self.assertEqual(bytes(sdk.flash.flash[16384:]), ORIGINAL[16384:]+IMAGE)
            self.assertFalse(any(a == p.DHCSR for a, _ in sdk.writes))
            calls = sdk.calls
            with self.assertRaises(ValueError): body.run()
            self.assertEqual(sdk.calls, calls)

    def test_retained_failure_restoration_never_acquires_new_breakpoint(self):
        first, sdk, _, archive, _ = fast_body(archive_fail='after-boot')
        with self.assertRaises(OSError): first.run()
        retained = dict(archive.saved, phase='POST_CAPTURE', release_attempted=False, boot_may_have_changed=True)
        body, sdk, logs, saved, _ = fast_body(retained=retained, boot=bytes(sdk.flash.flash[:65536]))
        body.active = True
        body.entry()
        body.capture('before')
        body.settle_controller()
        body.program()
        body.capture('after')
        self.assertTrue(body.post_verified)
        self.assertEqual(bytes(sdk.flash.flash), ORIGINAL+IMAGE)
        self.assertFalse(any(a in (p.COMP, p.PAUSE, p.DHCSR) for a, _ in sdk.writes))
        self.assertEqual(saved.saved['context'], retained['context'])

    def test_retained_drift_or_prior_release_blocks_restoration(self):
        retained = dict(phase='PROGRAM', release_attempted=False, boot_may_have_changed=True,
            before=dict(pause=4, fp=0x261, comparators=[0]*6, dfsr=0, demcr=0),
            context=dict(pc=probe.entry.WFI, xpsr=0x01000000, msp=0x20057fa0, special=0x04000000, fpccr=0))
        for problem in ('release', 'context', 'fp', 'dfsr', 'suffix'):
            item = copy.deepcopy(retained)
            if problem == 'release': item['release_attempted'] = True
            if problem == 'context': item['context']['msp'] -= 8
            body, sdk, _, _, _ = fast_body(retained=item, boot=PLAN.activated)
            if problem == 'fp': sdk.memory[0xe0002000] ^= 1
            if problem == 'dfsr': sdk.memory[p.REGS['dfsr']] |= 4
            if problem == 'suffix': sdk.flash.flash[20000] ^= 1
            with self.assertRaises(ValueError): body.run()
            self.assertFalse(sdk.flash.write_log)
            self.assertFalse(any(a in (p.COMP, p.PAUSE, p.DHCSR) for a, _ in sdk.writes))

    def test_full_pause_drift_before_settlement_cannot_clear_controller(self):
        body, sdk, _, _, _ = fast_body()
        body.active = True
        body.entry()
        body.direction = 'restore'
        _, status, ctrl, addr = p.flash.BANKS[0]
        sdk.memory.update({status: 0x20, ctrl: 1, addr: p.boot16.START})
        sdk.memory[p.PAUSE] ^= 1
        with self.assertRaises(ValueError): body.settle_controller()
        self.assertFalse(sdk.flash.write_log)

    def test_pending_restore_checks_full_suffix_and_app_before_any_ctrl_store(self):
        retained = dict(phase='PROGRAM', release_attempted=False, boot_may_have_changed=True,
            before=dict(pause=4, fp=0x261, comparators=[0]*6, dfsr=0, demcr=0),
            context=dict(pc=probe.entry.WFI, xpsr=0x01000000, msp=0x20057fa0, special=0x04000000, fpccr=0))
        for problem in (None, 'suffix', 'app'):
            body, sdk, logs, archive, _ = fast_body(retained=retained, boot=PLAN.activated)
            _, status, ctrl, addr = p.flash.BANKS[0]
            sdk.memory.update({status: 0x20, ctrl: 1, addr: p.boot16.START})
            if problem: sdk.flash.flash[20000 if problem == 'suffix' else 65536+20000] ^= 1
            body.active = True
            body.entry()
            if problem:
                with self.assertRaises(ValueError): body.capture('before')
                self.assertFalse(sdk.flash.write_log)
            else:
                body.capture('before')
                self.assertFalse(sdk.flash.write_log)
                self.assertEqual(len(archive.data['before-app']), p.APP_BYTES)
                body.settle_controller()
                self.assertEqual(sdk.flash.write_log, [(ctrl, 0), (ctrl, 0x80)])
                self.assertEqual(logs.gate.index, 24)

    def test_real_native_owner_with_57_sealed_logs(self):
        clock = Clock()
        paths = [BinaryBuffer('sdk-%03d.log' % n, '') for n in range(p.LOG_COUNT)]
        native = Native(paths, clock, None)
        native.log = lambda text: native.path.append(text) if native.path is not None else None
        native.model = Combined(clock)
        initial = []
        rows = []
        def persist(event, **fields): rows.append(dict(event=event, **fields))
        def collect(event, **fields):
            persist(event, **fields)
            initial.append(dict(event=event, **fields))
        archive = MemoryArchive()
        with mock.patch('recovery_entry.native_probe.guarded', side_effect=lambda f, *a, **k: f(*a)):
            dap = probe.base.Dap(native, paths[0], ROOT / '.cache/model-only.jlink', io.BytesIO())
            dap.sdk = probe.JournalSDK(native, collect, clock=clock)
            observation = probe.base.Observation(dap, collect, seconds=540, clock=clock)
            result = owner.execute(dap, observation, persist, initial, paths, record, lambda: 6000-clock.value,
                IMAGE, MAP, PLAN, archive, clock=clock, sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
        self.assertEqual(result['result'], 'BOOT16_PROGRAMMED_VERIFIED_CLOSED', result)
        self.assertEqual(len(result['logs']), 57)
        self.assertEqual(bytes(native.model.flash.flash), PLAN.activated+IMAGE)
        self.assertEqual(sum(name == 'JLINKARM_Close' for name, _ in native.calls), 1)
        reconciliation = audit.reconcile(paths, rows, result['dap'], record, PLAN, IMAGE, ORIGINAL)
        self.assertEqual(reconciliation['context'], archive.saved['context'])
        self.assertEqual(reconciliation['logs'], result['logs'])
        self.assertEqual(reconciliation['archives']['after-boot'], PLAN.activated)
        with self.assertRaises(ValueError): audit.reconcile(paths, rows, result['dap'], record, PLAN, IMAGE, ORIGINAL, failed=True)

    def test_original_failed_prefix_reconciles_but_uncertain_call_does_not(self):
        clock = Clock()
        paths = [BinaryBuffer('sdk-%03d.log' % n, '') for n in range(p.LOG_COUNT)]
        native = Native(paths, clock, None)
        native.log = lambda text: native.path.append(text) if native.path is not None else None
        native.model = Combined(clock)
        initial, rows = [], []
        def persist(event, **fields): rows.append(dict(event=event, **fields))
        def collect(event, **fields):
            persist(event, **fields)
            initial.append(dict(event=event, **fields))
        archive = MemoryArchive('after-boot')
        with mock.patch('recovery_entry.native_probe.guarded', side_effect=lambda f, *a, **k: f(*a)):
            dap = probe.base.Dap(native, paths[0], ROOT / '.cache/model-only.jlink', io.BytesIO())
            dap.sdk = probe.JournalSDK(native, collect, clock=clock)
            observation = probe.base.Observation(dap, collect, seconds=540, clock=clock)
            result = owner.execute(dap, observation, persist, initial, paths, record, lambda: 6000-clock.value,
                IMAGE, MAP, PLAN, archive, clock=clock, sleep=clock.sleep, guard=lambda f, *a, **k: f(*a))
        self.assertEqual(result['result'], 'FAILED')
        self.assertFalse(result['release_started'])
        selected = paths[:33]
        reconciliation = audit.reconcile(selected, rows, result['dap'], record, PLAN, IMAGE, ORIGINAL, failed=True)
        self.assertEqual(reconciliation['context'], archive.saved['context'])
        self.assertEqual(reconciliation['phase'], 'POST_CAPTURE')
        self.assertEqual(reconciliation['archives']['before-app'], IMAGE)
        changed = list(rows)
        row = next(i for i, row in enumerate(changed) if row['event'] == 'ap-call-returned')
        changed[row] = dict(changed[row], rc=-1)
        with self.assertRaises(ValueError): audit.reconcile(selected, changed, result['dap'], record, PLAN, IMAGE, ORIGINAL, failed=True)


if __name__ == '__main__': unittest.main()
