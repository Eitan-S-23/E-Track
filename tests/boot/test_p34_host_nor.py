import contextlib
import copy
import ctypes
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_entry import host_nor as hn
from recovery_entry.owner_probe import QSPI_REGS
from recovery_entry.dap_probe import Dap
import test_p34_control_probe as controls
import test_p34_owner_probe as owner_tests


class Model:
    def __init__(self):
        baseline = json.loads((ROOT/'.cache/p34-entry-owner1/worker.json').read_text())
        self.registers = {QSPI_REGS[k]: v for k, v in baseline['owner_samples'][0]['qspi'].items()}
        self.writes, self.reads, self.fifo, self.order = [], [], [], []
        self.sr1, self.sr2, self.id = 0, 2, bytes.fromhex('ef4018')
        self.halted, self.stuck_abort, self.stuck_complete = True, False, False
        self.fail_write, self.fail_read, self.operations = None, None, 0
    def owner(self):
        if not self.halted: raise ValueError('lost halt')
    def read(self, address):
        self.operations += 1
        self.reads.append(address)
        if self.fail_read == len(self.reads): raise KeyboardInterrupt('injected read fault')
        return self.registers[address]
    def write(self, address, value):
        self.operations += 1
        self.writes.append((address, value))
        old = self.registers.get(address)
        self.registers[address] = value
        if address == hn.CTRL:
            self.registers[address] = value | hn.IDLE | (hn.ABORT if self.stuck_abort else 0)
            if (old ^ value) & hn.XIP:
                self.fifo = []
                self.registers[hn.FIFO] = 1
        elif address == hn.CMDSTS:
            assert value == 1
            self.registers[address] = 0
        elif hn.BASE <= address <= hn.BASE+12:
            self.order.append(address-hn.BASE)
            if address == hn.BASE+12:
                assert self.order == [0, 4, 8, 12], self.order
                self.order = []
                opcode = value >> 24
                assert opcode in (5, 0x35, 0x9f)
                assert self.registers[hn.BASE] == 0
                assert self.registers[hn.BASE+4] == 0x1000000
                assert self.registers[hn.BASE+8] == (3 if opcode == 0x9f else 0)
                assert value & 0xffffff == (0 if opcode == 0x9f else 0xc)
                self.registers[hn.CMDSTS] = 0 if self.stuck_complete else 1
                if opcode == 0x9f:
                    self.fifo = list(self.id)
                    self.registers[hn.FIFO] = 3
                else:
                    self.registers[hn.RSTS] = self.sr1 if opcode == 5 else self.sr2
        if self.fail_write == len(self.writes): raise OSError('delivered write, failed return')
    def rdid_bytes(self):
        assert len(self.fifo) == 3 and self.registers[hn.FIFO] == 3
        data = bytes(self.fifo)
        self.fifo = []
        self.registers[hn.FIFO] = 1
        return data


class SDK(controls.SDK):
    def __init__(self, model):
        super().__init__()
        self.model, self.fifo_reads, self.nor_wrapped = model, [], set()
    def __getattr__(self, name):
        func = super().__getattr__(name)
        if name not in self.nor_wrapped:
            old = func.callback
            def invoke(*args):
                if name == 'JLINKARM_CORESIGHT_ReadAPDPReg' and args[:2] == (3, 1) and self.bank == 0:
                    if self.tar == hn.DT:
                        assert self.csw & 0x37 == 0, 'not byte/no-increment'
                        assert self.model.fifo, 'FIFO overread'
                        self.fifo_reads.append((self.tar, self.csw))
                        value = self.model.fifo.pop(0)
                        if not self.model.fifo: self.model.registers[hn.FIFO] = 1
                        ctypes.cast(args[2], ctypes.POINTER(ctypes.c_uint32))[0] = value
                        return 0
                    if self.tar in self.model.registers:
                        ctypes.cast(args[2], ctypes.POINTER(ctypes.c_uint32))[0] = self.model.read(self.tar)
                        self.tar += 4
                        return 0
                if name == 'JLINKARM_CORESIGHT_WriteAPDPReg' and args[:2] == (3, 1) and self.tar in self.model.registers:
                    assert self.csw & 7 == 2, 'MMIO not word width'
                    self.model.write(self.tar, args[2])
                    self.tar += 4
                    return 0
                return old(*args)
            func.callback = invoke
            self.nor_wrapped.add(name)
        return func


class StatusTests(unittest.TestCase):
    def run_model(self, model=None):
        m = model or Model()
        status = hn.Status(m, lambda *a, **k: None)
        return m, status

    def test_complete_sequence_restores_only_passive_configuration(self):
        m, s = self.run_model()
        result = s.execute()
        self.assertEqual(result['samples'], [dict(sr1=0, sr2=2, jedec='ef4018')]*2)
        self.assertTrue(s.restored)
        self.assertFalse(result['nor_write_admitted'])
        self.assertFalse(result['physical_variant_proven'])
        self.assertEqual([v for a, v in m.writes if a == hn.CTRL], [hn.XIP|7, 7, hn.XIP|7, hn.XIP])
        self.assertEqual([v for a, v in m.writes if a == hn.BASE+12], [0x0500000c, 0x3500000c, 0x9f000000]*2)

    def test_stale_completion_rejected_before_commands(self):
        m, s = self.run_model()
        m.registers[hn.CMDSTS] = 1
        with self.assertRaises(ValueError): s.execute()
        self.assertEqual(m.writes, [])

    def test_stuck_abort_never_issues_command(self):
        m, s = self.run_model(); m.stuck_abort = True
        with self.assertRaisesRegex(ValueError, 'wait exhausted'): s.execute()
        self.assertEqual(m.writes, [(hn.CTRL, hn.XIP|7)])

    def test_no_complete_never_reads_rsts_or_acknowledges(self):
        m, s = self.run_model(); m.stuck_complete = True
        with self.assertRaisesRegex(ValueError, 'wait exhausted'): s.execute()
        self.assertNotIn(hn.CMDSTS, [a for a, _ in m.writes])
        self.assertEqual([v for a, v in m.writes if a == hn.BASE+12], [0x0500000c])

    def test_every_delivered_write_failure_latches_and_never_cleans_up(self):
        m, s = self.run_model(); s.execute()
        total = len(m.writes)
        for n in range(1, total+1):
            m, s = self.run_model(); m.fail_write = n
            with self.assertRaises(OSError): s.execute()
            self.assertEqual(len(m.writes), n)
            with self.assertRaises(ValueError): s.write(hn.CTRL, hn.XIP)
            self.assertEqual(len(m.writes), n)
            self.assertFalse(s.restored)

    def test_every_read_baseexception_latches_without_cleanup(self):
        m, s = self.run_model(); s.execute(); total = len(m.reads)
        for n in range(1, total+1):
            m, s = self.run_model(); m.fail_read = n
            with self.assertRaises(KeyboardInterrupt): s.execute()
            count = len(m.writes)
            with self.assertRaises(ValueError): s.write(hn.CTRL, hn.XIP)
            self.assertEqual(len(m.writes), count)

    def test_busy_wel_suspended_not_identified_or_restored(self):
        for a, v in (('sr1', 1), ('sr1', 2), ('sr2', 0x82)):
            m, s = self.run_model(); setattr(m, a, v)
            with self.assertRaisesRegex(ValueError, 'WIP/WEL/SUS'): s.execute()
            self.assertNotIn(0x9f000000, [v for a, v in m.writes if a == hn.BASE+12])
            self.assertFalse(s.restored)

    def test_wrong_identity_and_missing_qe_not_restored(self):
        for field, value in (('id', b'\xff'*3), ('id', bytes.fromhex('ef4017')), ('sr2', 0)):
            m, s = self.run_model(); setattr(m, field, value)
            with self.assertRaises(ValueError): s.execute()
            self.assertFalse(s.restored)

    def test_status_instability_rejected(self):
        m, s = self.run_model(); old = m.rdid_bytes
        def changed():
            data = old(); m.sr2 ^= 0x10; return data
        m.rdid_bytes = changed
        with self.assertRaisesRegex(ValueError, 'changed between'): s.execute()
        self.assertFalse(s.restored)

    def test_deadline_latches_no_restore(self):
        m = Model()
        s = hn.Status(m, lambda *a, **k: None, seconds=1, clock=lambda: m.operations/20)
        with self.assertRaisesRegex(ValueError, 'deadline'): s.execute()
        count = len(m.writes)
        with self.assertRaises(ValueError): s.execute()
        self.assertEqual(len(m.writes), count)

    def test_wrong_passive_configuration_rejected(self):
        for k in hn.CONFIG:
            m, s = self.run_model(); m.registers[QSPI_REGS[k]] ^= 1
            with self.assertRaises(ValueError): s.execute()
            self.assertEqual(m.writes, [])

    def test_exact_dma_profile_and_clock_required(self):
        value = json.loads((ROOT/'.cache/p34-entry-owner1/worker.json').read_text())['retained']['state_samples'][0]
        hn.qualify_masters(value)
        changes = [(k, value['raw'][k]^1) for k in hn.CLOCK]
        changes += [('edma_1', 1), ('dma1_1', 1), ('dma1_3', 0x10b3), ('dma2_4', 0x6a81),
                    ('display_dma_count', 1), ('sd_dma_count', 1), ('qspi_ctrl2', 1),
                    ('sd_dma_memory', 0x90000000), ('display_dma_memory', 0x90000000)]
        for k, v in changes:
            changed = copy.deepcopy(value); changed['raw'][k] = v
            with self.assertRaises(ValueError): hn.qualify_masters(changed)

    def test_real_port_exact_byte_fifo_and_no_readonly_dap_widening(self):
        model = Model(); sdk = SDK(model)
        dap = Dap(sdk, ROOT/'.cache/fake.log', ROOT/'.cache/fake.jlink', io.BytesIO())
        dap.open(); dap.connect()
        sdk.memory[controls.DHCSR] = 0x30001; sdk.memory[controls.PAUSE] = 0x1000
        control = controls.Control(dap, controls.Observer(dap), lambda *a, **k: None, bytes(96), retained=True)
        port = hn.Port(control, lambda *a, **k: None)
        status = hn.Status(port, lambda *a, **k: None)
        status.execute()
        self.assertEqual(len(sdk.fifo_reads), 6)
        self.assertEqual(dap._read_reg(0, 1), dap.word_csw)
        with self.assertRaises(ValueError): dap.read(hn.DT, 4)
        for address, value in ((hn.BASE+12, 0x06000002), (hn.BASE+12, 0x20000002),
                               (hn.BASE+12, 0x02000002), (hn.CTRL2, 0), (hn.DT, 0),
                               (0xe000ed0c, 0x05fa0004)):
            with self.assertRaises(ValueError): port.write(address, value)
        control.close()
        self.assertTrue(dap.close_returned)

    def test_partial_fifo_consumption_no_config_cleanup(self):
        m, s = self.run_model()
        def partial():
            m.fifo.pop(0); raise OSError('partial native FIFO read')
        m.rdid_bytes = partial
        with self.assertRaises(OSError): s.execute()
        self.assertEqual(len(m.fifo), 2)
        self.assertEqual([v for a, v in m.writes if a == hn.CTRL], [hn.XIP|7, 7])

    def fifo_fixture(self):
        m = Model(); sdk = SDK(m)
        dap = Dap(sdk, ROOT/'.cache/fake.log', ROOT/'.cache/fake.jlink', io.BytesIO())
        dap.open(); dap.connect()
        sdk.memory[controls.DHCSR] = 0x30001; sdk.memory[controls.PAUSE] = 0x1000
        control = controls.Control(dap, controls.Observer(dap), lambda *a, **k: None, bytes(96), retained=True)
        port = hn.Port(control, lambda *a, **k: None)
        status = hn.Status(port, lambda *a, **k: None)
        m.fifo = [0xef, 0x40, 0x18]; m.registers[hn.FIFO] = 3
        return m, sdk, dap, control, port, status

    def test_each_native_fifo_substep_error_restores_ap_not_qspi(self):
        m, sdk, dap, ctrl, p, s = self.fifo_fixture()
        before = len(sdk.calls)
        s.call(p.rdid_bytes)
        total = len(sdk.calls)-before
        ctrl.close()
        for mode in ('error-return', 'baseexception'):
            for fail_at in range(1, total+1):
                m, sdk, dap, ctrl, p, s = self.fifo_fixture()
                count = [0]
                for name in ('JLINKARM_CORESIGHT_ReadAPDPReg', 'JLINKARM_CORESIGHT_WriteAPDPReg'):
                    f = getattr(sdk, name); old = f.callback
                    def wrapped(*args, old=old):
                        value = old(*args); count[0] += 1
                        if count[0] == fail_at:
                            if mode == 'baseexception': raise KeyboardInterrupt('SDK callback fault')
                            return -1
                        return value
                    f.callback = wrapped
                with self.assertRaises((ValueError, KeyboardInterrupt)):
                    s.call(p.rdid_bytes)
                consumed = len(sdk.fifo_reads)
                with self.assertRaises(ValueError): s.write(hn.CTRL, hn.XIP)
                p.restore_ap()
                ctrl.close()
                self.assertEqual(sdk.csw, dap.original_csw, (mode, fail_at))
                self.assertTrue(dap.close_returned)
                self.assertEqual(len(sdk.fifo_reads), consumed)
                self.assertEqual(m.writes, [])

    def test_sticky_error_stops_at_first_or_second_consumed_byte(self):
        for byte in (1, 2):
            m, sdk, dap, ctrl, p, s = self.fifo_fixture()
            old = sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback
            def fault(*args):
                value = old(*args)
                if len(sdk.fifo_reads) == byte: sdk.dp |= 0x20
                return value
            sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback = fault
            with self.assertRaisesRegex(ValueError, 'sticky error'):
                s.call(p.rdid_bytes)
            self.assertEqual(len(sdk.fifo_reads), byte)
            with self.assertRaises(ValueError): p.restore_ap()
            with self.assertRaises(ValueError): ctrl.close()
            self.assertTrue(dap.close_returned)
            self.assertEqual(m.writes, [])

    def test_lost_halt_stops_before_switch(self):
        m, s = self.run_model(); m.halted = False
        with self.assertRaises(ValueError): s.execute()
        self.assertEqual(m.writes, [])

    def test_full_worker_mocked_native_boundary(self):
        import p34_host_nor as run
        store = run.cli.Store(ROOT)
        out = store.checked(Path(os.environ['P34_TEST_OUT'])/'case-worker')
        run.preflight(store, out)
        model = Model(); sdk = SDK(model)
        baseline = store.read(ROOT/'.cache/p34-entry-owner1/worker.json')
        raw = baseline['retained']['state_samples'][0]['raw']
        sdk.memory.update({controls.REGISTERS[k]: v for k, v in raw.items()})
        fixture = owner_tests.Reader(); sdk.memory.update(fixture.memory)
        previous = store.read(ROOT/'.cache/p34-entry-wfi1/worker.json')
        ctx = previous['context']
        sdk.memory.update({controls.DHCSR:0x30001, controls.PAUSE:0x1000,
                           0xe000ef34:ctx['fpccr'], 0x40002c00:0, 0x20053538:0x104, 0x200007e8:0})
        sdk.core.update({15:ctx['pc'], 16:ctx['xpsr'], 17:ctx['msp'], 20:ctx['control']<<24})
        image = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()
        for off in range(0x400, 0x460, 4): sdk.memory[0x08010000+off] = int.from_bytes(image[off:off+4], 'little')
        op = owner_tests.op; address = op.PAGE_NAME & ~3
        data = (b'\0'*(op.PAGE_NAME-address)+op.PAGE_TEXT).ljust(24, b'\0')
        for i in range(0, 24, 4): sdk.memory[address+i] = int.from_bytes(data[i:i+4], 'little')
        class Observer(controls.Observer):
            def __init__(self, dap, emit, seconds): super().__init__(dap)
            def connect(self): self.dap.open(); self.dap.connect()
            def _check(self): pass
        store.write(out/'plan.json', dict(inputs=[run.cli.record(p) for p in run.SOURCES],
                    out=str(out), native_history_approved=str(run.base.HISTORY)))
        with mock.patch.object(run.base, 'in_job', return_value=True), \
             mock.patch.object(run.base, 'native_presence', return_value=dict(debugger_processes=[])), \
             mock.patch.object(run.base, 'guarded', return_value=sdk), \
             mock.patch.object(run.base, 'Observation', Observer), \
             mock.patch.object(run.os, 'add_dll_directory', return_value=contextlib.nullcontext()):
            self.assertEqual(run.worker(store, out), 0)
        result = store.read(out/'worker.json')
        self.assertEqual(result['result'], 'HOST_NOR_STATUS_RESTORED_RETAINED')
        self.assertTrue(result['close_returned'])
        self.assertEqual(result['nor_payload_bytes_written'], 0)


if __name__ == '__main__': unittest.main()
