import ctypes
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_entry import host_nor as hn, host_nor_mapped as mapped
from recovery_entry.dap_probe import Dap
import test_p34_host_nor_read as prior


class SDK(prior.SDK):
    def __init__(self, model):
        super().__init__(model)
        self.mapped_wrapped, self.mapped_reads = set(), []
    def __getattr__(self, name):
        func = super().__getattr__(name)
        if name not in self.mapped_wrapped:
            old = func.callback
            def invoke(*args):
                if name == 'JLINKARM_CORESIGHT_ReadAPDPReg' and args[:2] == (3, 1) and self.bank == 0 and mapped.MAPPED <= self.tar < mapped.MAPPED+0x1000000:
                    assert self.csw & 0x37 == 0x12
                    assert self.model.registers[mapped.XIP3] & 1
                    self.model.registers[mapped.XIP3] |= 8
                    address = self.tar-mapped.MAPPED
                    self.mapped_reads.append(address)
                    data = self.model.payload(3, address, 4)
                    ctypes.cast(args[2], ctypes.POINTER(ctypes.c_uint32))[0] = int.from_bytes(data, 'little')
                    self.tar = (self.tar & ~1023) | ((self.tar+4) & 1023)
                    return 0
                return old(*args)
            func.callback = invoke; self.mapped_wrapped.add(name)
        return func


def fixture():
    m = prior.Model(); sdk = SDK(m)
    dap = Dap(sdk, ROOT/'.cache/fake.log', ROOT/'.cache/fake.jlink', io.BytesIO())
    dap.open(); dap.connect()
    controls = prior.prior.controls
    sdk.memory[controls.DHCSR] = 0x30001; sdk.memory[controls.PAUSE] = 0x1000
    ctrl = controls.Control(dap, controls.Observer(dap), lambda *a, **k: None, bytes(96), retained=True)
    port = mapped.Port(ctrl, lambda *a, **k: None)
    reader = mapped.Reader(port, lambda *a, **k: None)
    return m, sdk, dap, ctrl, port, reader


class MappedTests(unittest.TestCase):
    def test_complete_against_fifo_model_with_cache_state_changes(self):
        m, sdk, dap, ctrl, p, r = fixture()
        result = mapped.collect(r)
        self.assertEqual(bytes.fromhex(result['candidate_prefix_hex']), m.image[:4096])
        self.assertEqual(bytes.fromhex(result['recovery_prefix_hex']), bytes(range(128)))
        self.assertEqual(bytes.fromhex(result['preserved_boundary_hex']), bytes(range(128)))
        self.assertEqual(len(sdk.mapped_reads), (4096+256)//4)
        self.assertTrue(r.restored)
        self.assertEqual([v for a, v in m.writes if a == mapped.XIP3], [1, 0])
        self.assertTrue(all(a < mapped.MAPPED or a >= mapped.MAPPED+0x1000000 for a, _ in m.writes))
        ctrl.close()

    def test_tar_alignment_and_physical_bounds(self):
        m, sdk, dap, ctrl, p, r = fixture()
        for address, size in ((0, 0), (0, 1028), (1, 4), (0, 3), (-4, 4), (1020, 8),
                              (0x1000000, 4), (0xfffffc, 8)):
            with self.assertRaises(ValueError): p.mapped(address, size)
        self.assertEqual(sdk.mapped_reads, [])
        ctrl.close()

    def test_bypass_is_mandatory_and_mode_is_qualified(self):
        for address, value in ((mapped.XIP3, 0), (hn.CTRL, hn.XIP|hn.IDLE), (hn.CTRL2, 1)):
            m, sdk, dap, ctrl, p, r = fixture()
            m.registers.update({hn.CTRL:hn.XIP|hn.IDLE|7, mapped.XIP3:1})
            m.registers[address] = value
            with self.assertRaises(ValueError): p.mapped(0x1000, 4)
            self.assertEqual(sdk.mapped_reads, [])
            ctrl.close()

    def test_failed_bypass_store_never_replayed(self):
        for phase in (1, 2):
            m, sdk, dap, ctrl, p, r = fixture()
            old = m.write; bypass_writes = [0]
            def failed(address, value):
                old(address, value)
                if address == mapped.XIP3:
                    bypass_writes[0] += 1
                    if bypass_writes[0] == phase: raise OSError('bypass delivered/error return')
            m.write = failed
            with self.assertRaises(OSError): mapped.collect(r)
            count = len(m.writes)
            with self.assertRaises(ValueError): r.finish()
            self.assertEqual(len(m.writes), count)
            ctrl.close()

    def test_sticky_error_invalidates_entire_chunk_before_publish(self):
        m, sdk, dap, ctrl, p, r = fixture()
        r.open(); r.call(p.bypass, True); r.transition(hn.XIP|7)
        old = sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback
        def fault(*args):
            result = old(*args)
            if len(sdk.mapped_reads) == 1: sdk.dp |= 0x20
            return result
        sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback = fault
        writes = len(m.writes)
        with self.assertRaisesRegex(ValueError, 'sticky error'): r.call(p.mapped, 0x1000, 1024)
        self.assertEqual(len(sdk.mapped_reads), 256)
        with self.assertRaises(ValueError): r.finish()
        self.assertEqual(len(m.writes), writes)
        with self.assertRaises(ValueError): ctrl.close()
        self.assertTrue(dap.close_returned)

    def test_native_error_stops_before_remaining_mapped_reads(self):
        for fail_word in (1, 64, 256):
            m, sdk, dap, ctrl, p, r = fixture()
            r.open(); r.call(p.bypass, True); r.transition(hn.XIP|7)
            old = sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback
            def fault(*args):
                result = old(*args)
                return -1 if len(sdk.mapped_reads) == fail_word else result
            sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback = fault
            count = len(m.writes)
            with self.assertRaises(ValueError): r.call(p.mapped, 0x1000, 1024)
            self.assertEqual(len(sdk.mapped_reads), fail_word)
            with self.assertRaises(ValueError): r.finish()
            self.assertEqual(len(m.writes), count)
            # Release the deliberately persistent mock failure before AP-only close.
            sdk.JLINKARM_CORESIGHT_ReadAPDPReg.callback = old
            ctrl.close()


if __name__ == '__main__': unittest.main()
