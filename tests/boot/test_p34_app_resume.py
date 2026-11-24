import contextlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_entry import app_resume as ar
from recovery_entry.dap_probe import Dap
import test_p34_control_probe as controls
import test_p34_owner_probe as owner_tests

IMAGE = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()


def baseline():
    values = {key: 0 for key in ar.REGISTERS}
    values.update(dhcsr=0x30003, vtor=0x08010000, systick_ctrl=0x10007, systick_load=287999,
                  systick_value=12000, cfsr=0x82, hfsr=0x40000000, shcsr=0x70000, icsr=0x04000000)
    return values


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class Model:
    def __init__(self, clock):
        self.clock, self.values = clock, baseline()
        self.attempted, self.returned, self.running, self.calls = False, False, False, 0
        self.write_error, self.deliver = False, True
        self.rates = dict(millis=1000, loop=100, feed=100)
        self.fault, self.reset = False, False
        self.freeze_at, self.fault_at = None, 2
    def snapshot(self, *, halted=False):
        v = dict(self.values)
        if self.running:
            v['dhcsr'] = 0x10001
            tick = self.clock() if self.freeze_at is None else min(self.clock(), self.freeze_at)
            for key, rate in self.rates.items(): v[key] = (v[key]+int(tick*rate)) & 0xffffffff
            if self.fault and self.clock() >= self.fault_at: v['cfsr'] ^= 0x100
            if self.reset and self.clock() >= self.fault_at: raise ValueError('reset observed')
        return v
    def resume_once(self):
        if self.attempted: raise AssertionError('resume replay')
        self.attempted = True; self.calls += 1
        self.running = self.deliver
        if self.write_error: raise OSError('uncertain resume return')
        self.returned = True


class SDK(controls.SDK):
    def __init__(self, clock):
        super().__init__(); self.clock, self.running, self.resume_wrapped = clock, False, set()
        self.memory.update({address: baseline()[key] for key, address in ar.REGISTERS.items()})
        for offset in range(0, len(IMAGE), 4):
            self.memory[0x08010000+offset] = int.from_bytes(IMAGE[offset:offset+4], 'little')
    def __getattr__(self, name):
        f = super().__getattr__(name)
        if name not in self.resume_wrapped:
            old = f.callback
            def wrapped(*args):
                address = self.tar
                if self.running and name == 'JLINKARM_CORESIGHT_ReadAPDPReg' and args[:2] == (3, 1):
                    for key, rate in (('millis', 1000), ('loop', 100), ('feed', 100)):
                        self.memory[ar.REGISTERS[key]] = int(self.clock()*rate) & 0xffffffff
                result = old(*args)
                if name == 'JLINKARM_CORESIGHT_WriteAPDPReg' and args[:2] == (3, 1) and address == ar.DHCSR:
                    assert args[2] == 0xa05f0001
                    self.memory[ar.DHCSR] = 0x10001; self.running = True
                return result
            f.callback = wrapped; self.resume_wrapped.add(name)
        return f


class ResumeTests(unittest.TestCase):
    def test_good_resume_uses_twenty_seconds_of_loop_feed_and_ticks(self):
        clock = Clock(); p = Model(clock)
        result = ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)
        self.assertEqual(result['result'], 'ORIGINAL_APP_RESUMED_STABLE')
        self.assertEqual(p.calls, 1)
        self.assertEqual(result['running']['elapsed_seconds'], 20)

    def test_historical_fault_flags_and_pending_systick_allowed(self):
        ar.entry(baseline(), IMAGE[:524])

    def test_bad_entry_never_issues_resume(self):
        cases = [('dhcsr', 0x10001), ('dhcsr', 0x3000b), ('systick_ctrl', 5),
                 ('systick_load', 0), ('systick_value', 288000), ('shpr3', 0xff000000),
                 ('scr', 2), ('scr', 4), ('icsr', 0x10000000), ('icsr', 0x80000000),
                 ('icsr', 15), ('shcsr', 0x8000), ('shcsr', 1), ('demcr', 0x20000)]
        for key, value in cases:
            clock = Clock(); p = Model(clock); p.values[key] = value
            with self.assertRaises(ValueError): ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)
            self.assertEqual(p.calls, 0)

    def test_pending_external_default_or_absent_vector_rejected(self):
        v = baseline(); v['iser0'] = v['ispr0'] = 1
        vectors = bytearray(IMAGE[:524]); struct.pack_into('<I', vectors, 64, 0x0801b835)
        with self.assertRaises(ValueError): ar.entry(v, bytes(vectors))
        v = baseline(); v['iser3'] = v['ispr3'] = 0x80000000
        with self.assertRaises(ValueError): ar.entry(v, IMAGE[:524])

    def test_delivered_write_error_observed_without_replay(self):
        clock = Clock(); p = Model(clock); p.write_error = True
        result = ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)
        self.assertEqual(result['result'], 'ORIGINAL_APP_RUNNING_AFTER_UNCERTAIN_RESUME')
        self.assertEqual(p.calls, 1)
        self.assertFalse(result['resume_returned'])

    def test_undelivered_write_error_does_not_retry_or_rehalt(self):
        clock = Clock(); p = Model(clock); p.write_error, p.deliver = True, False
        with self.assertRaises(ValueError): ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)
        self.assertEqual(p.calls, 1)
        self.assertFalse(p.running)

    def test_ticks_alone_do_not_prove_main_loop_health(self):
        for key in ('loop', 'feed', 'millis'):
            clock = Clock(); p = Model(clock); p.rates[key] = 0
            with self.assertRaises(ValueError): ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)
            self.assertEqual(p.calls, 1)

    def test_final_five_second_stall_is_not_stable(self):
        clock = Clock(); p = Model(clock); p.freeze_at = 15
        with self.assertRaisesRegex(ValueError, 'stagnant'):
            ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)
        self.assertEqual(p.calls, 1)

    def test_reset_at_final_sample_is_detected(self):
        clock = Clock(); p = Model(clock); p.reset, p.fault_at = True, 20
        with self.assertRaisesRegex(ValueError, 'reset'):
            ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)
        self.assertEqual(p.calls, 1)

    def test_post_audit_sdk_or_event_change_blocks_eligibility(self):
        import p34_app_resume as run
        store = run.cli.Store(ROOT)
        for name in ('sdk.log', 'events.jsonl'):
            directory = store.checked(Path(os.environ['P34_TEST_OUT'])/('audit-'+name))
            paths = [store.checked(directory/n) for n in ('sdk.log', 'events.jsonl')]
            records = [store.raw(p, b'original evidence') for p in paths]
            audit = dict(traces=[dict(evidence=records)], script=run.cli.record(ROOT/'Tools/ota/p34_nor_audit.py'))
            run.audit_bindings(store, audit, paths)
            with store.checked(directory/name).open('ab') as stream: stream.write(b' changed')
            with self.assertRaises(RuntimeError): run.audit_bindings(store, audit, paths)

    def test_counter_wrap_is_bounded_and_supported(self):
        clock = Clock(); p = Model(clock)
        p.values.update(millis=0xffffff00, loop=0xffffff00, feed=0xffffff00)
        self.assertEqual(ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)['result'], 'ORIGINAL_APP_RESUMED_STABLE')

    def test_fault_change_or_reset_stops_observation_not_control(self):
        for key in ('fault', 'reset'):
            clock = Clock(); p = Model(clock); setattr(p, key, True)
            with self.assertRaises(ValueError): ar.execute(p, IMAGE[:524], clock=clock, sleep=clock.sleep)
            self.assertEqual(p.calls, 1)

    def test_real_dap_port_emits_only_one_dhcsr_store(self):
        clock = Clock(); sdk = SDK(clock)
        dap = Dap(sdk, ROOT/'.cache/fake.log', ROOT/'.cache/fake.jlink', io.BytesIO())
        dap.open(); dap.connect()
        port = ar.Port(dap, lambda *a, **k: None, IMAGE[0x400:0x460])
        result = ar.execute(port, IMAGE[:524], clock=clock, sleep=clock.sleep)
        self.assertEqual(result['result'], 'ORIGINAL_APP_RESUMED_STABLE')
        stores = [args[2] for name, args in sdk.calls if name == 'JLINKARM_CORESIGHT_WriteAPDPReg' and args[:2] == (3, 1)]
        self.assertEqual(stores, [0xa05f0001])
        with self.assertRaises(ValueError): port.resume_once()
        for address in (0xe000ed0c, 0x40003000, 0x200539e4):
            with self.assertRaises(ValueError): port.read(address)
        dap.close()

    def test_header_mismatch_or_reset_sticky_never_resumes(self):
        for kind in ('header', 'reset'):
            clock = Clock(); sdk = SDK(clock)
            dap = Dap(sdk, ROOT/'.cache/fake.log', ROOT/'.cache/fake.jlink', io.BytesIO())
            dap.open(); dap.connect()
            port = ar.Port(dap, lambda *a, **k: None, IMAGE[0x400:0x460])
            if kind == 'header': sdk.memory[0x08010400] ^= 1
            else: sdk.memory[ar.DHCSR] |= 0x02000000
            with self.assertRaises(ValueError): port.snapshot(halted=True)
            self.assertFalse(port.attempted)
            if kind == 'reset':
                sdk.memory[ar.DHCSR] &= ~0x02000000
                with self.assertRaises(ValueError): port.snapshot(halted=True)
            dap.close()

    def worker_case(self, *, consumed_reset=False):
        import p34_app_resume as run
        name = 'case-worker-reset-latch' if consumed_reset else 'case-worker'
        store = run.cli.Store(ROOT); out = store.checked(Path(os.environ['P34_TEST_OUT'])/name)
        run.preflight(store, out)
        clock = Clock(); sdk = SDK(clock)
        old = store.read(ROOT/'.cache/p34-entry-owner1/worker.json')
        raw = old['retained']['state_samples'][0]['raw']
        sdk.memory.update({controls.REGISTERS[k]: v for k, v in raw.items()})
        sdk.memory.update({a: baseline()[k] for k, a in ar.REGISTERS.items()})
        for k, v in old['owner_samples'][0]['qspi'].items(): sdk.memory[owner_tests.op.QSPI_REGS[k]] = v
        sdk.memory.update(owner_tests.Reader().memory)
        ctx = old['retained']['context']
        sdk.memory.update({controls.PAUSE:0x1000, 0xe000ef34:ctx['fpccr'], 0x40002c00:0,
                           0x20053538:0x104, 0x200007e8:0})
        sdk.core.update({15:ctx['pc'], 16:ctx['xpsr'], 17:ctx['msp'], 20:ctx['control']<<24})
        store.write(out/'plan.json', dict(inputs=[run.cli.record(p) for p in run.SOURCES], out=str(out),
            native_history_approved=str(run.base.HISTORY), recovery=[], audit=str(out/'mock-audit.json')))
        class Observer(controls.Observer):
            def __init__(self, dap, emit, seconds): super().__init__(dap)
            def connect(self): self.dap.open(); self.dap.connect()
            def _check(self): pass
        execute = ar.execute
        original_owners = run.prior.prior.prior.owners
        def owners(control, dap, emit):
            result = original_owners(control, dap, emit)
            if consumed_reset:
                control.reset_seen = True
                sdk.memory[ar.DHCSR] &= ~0x02000000
            return result
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(run, 'recovery_inputs', return_value=[]), \
             mock.patch.object(run.base, 'native_presence', return_value=dict(debugger_processes=[])), \
             mock.patch.object(run.base, 'guarded', return_value=sdk), \
             mock.patch.object(run.base, 'Observation', Observer), \
             mock.patch.object(run.prior.prior.prior, 'owners', side_effect=owners), \
             mock.patch.object(run.ar, 'execute', side_effect=lambda p, v: execute(p, v, clock=clock, sleep=clock.sleep)), \
             mock.patch.object(run.os, 'add_dll_directory', return_value=contextlib.nullcontext()):
            self.assertEqual(run.worker(store, out), 1 if consumed_reset else 0)
        result = store.read(out/'worker.json')
        self.assertEqual(result['result'], 'FAILED' if consumed_reset else 'ORIGINAL_APP_RESUMED_STABLE')
        if consumed_reset:
            self.assertFalse(sdk.running)
            self.assertNotIn('resume', result)
            self.assertNotIn('resume-write-attempt', (out/'events.jsonl').read_text())
            stores = [args[2] for name, args in sdk.calls
                      if name == 'JLINKARM_CORESIGHT_WriteAPDPReg' and args[:2] == (3, 1)]
            self.assertNotIn(0xa05f0001, stores)
        self.assertTrue(result['close_returned'])
        self.assertFalse(result['reset_performed'])

    def test_worker_mocked_recovery_gate_and_native_boundary(self):
        self.worker_case()

    def test_consumed_control_reset_latch_blocks_resume_with_raw_flag_clear(self):
        self.worker_case(consumed_reset=True)


if __name__ == '__main__': unittest.main()
