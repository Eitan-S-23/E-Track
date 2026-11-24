import contextlib
import ctypes
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
import p34_finalized_reader_device as run
import test_p34_finalized_reader as port_tests
from recovery_entry.finalized_reader import Reader

ORIGINAL = (ROOT/'.cache/p34-native-image1/app-readback.bin').read_bytes()


class SDK(port_tests.SDK):
    def JLINKARM_CORESIGHT_ReadAPDPReg(self, index, ap, pointer):
        address = self.tar
        rc = super().JLINKARM_CORESIGHT_ReadAPDPReg(index, ap, pointer)
        if (index,ap) == (3,1) and address == run.capture.VTOR:
            ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))[0] = 0x08010000
        return rc


class Dap:
    inject_post_reset = False
    def __init__(self, sdk, *unused):
        self.sdk, self.ready, self.callback_error = sdk, True, None
        self.word_csw, self.close_returned, self.metadata = sdk.csw, False, {}
        self.idle_reads=0
    def read(self, address, size):
        assert address in (0x20052a54,0x20052b34) and size == 4
        self.idle_reads+=1
        if self.inject_post_reset and self.idle_reads==5:self.sdk.dhcsr|=0x02000000
        return bytes(4)
    def close(self): self.ready=False; self.close_returned=True


class DeviceTests(unittest.TestCase):
    def reader(self, raw):
        sdk = SDK(raw); dap = Dap(sdk)
        state = dict(owned=True, connection_generation='c1', boot_generation=0, reset_seen=False)
        reader = Reader(dap, lambda *a,**k:None, lambda:dict(state), connection_generation='c1', boot_generation=0,
                        guard=lambda fn,*args,seconds:fn(*args))
        return reader, sdk

    def test_expected_old_prefix_and_unclassified_tail(self):
        raw = ORIGINAL+b'Z'*1992; reader,sdk = self.reader(raw)
        actual, reads = run.capture_old(reader, ORIGINAL)
        self.assertEqual(actual,raw); self.assertEqual(len(reads),158)
        self.assertEqual(reader.api_reads,158)
        self.assertEqual(run.reject_finalized(raw),'EXPECTED_OLD_IMAGE_REJECTION')
        self.assertTrue(all(c[1:3] == (1,1) for c in sdk.calls if c[0] == 'write'))

    def test_changed_old_prefix_is_not_qualification(self):
        raw = bytearray(ORIGINAL+b'Z'*1992); raw[0x1000] ^= 1
        reader,_ = self.reader(bytes(raw))
        with self.assertRaisesRegex(RuntimeError, 'prefix changed'): run.capture_old(reader,ORIGINAL)

    def test_reader_error_is_not_expected_negative_admission(self):
        reader,sdk = self.reader(ORIGINAL+b'Z'*1992); sdk.fail_at=1
        with self.assertRaises(ValueError): run.capture_old(reader,ORIGINAL)
        self.assertEqual(len(sdk.calls),1)

    def test_final_identity_and_phase_are_checked_after_full_read(self):
        for kind in ('header','halt'):
            reader,sdk = self.reader(ORIGINAL+b'Z'*1992)
            original_read = sdk.JLINKARM_CORESIGHT_ReadAPDPReg
            def read(index,ap,pointer):
                address=sdk.tar
                result=original_read(index,ap,pointer)
                if (index,ap)==(3,1) and address==0x08010000+619580-4:
                    if kind=='header':
                        changed=bytearray(sdk.image);changed[0x400]^=1;sdk.image=bytes(changed)
                    else: sdk.dhcsr|=0x20000
                return result
            sdk.JLINKARM_CORESIGHT_ReadAPDPReg=read
            with self.assertRaises((RuntimeError,ValueError)): run.capture_old(reader,ORIGINAL)

    def test_finalized_image_is_not_a_negative_policy_result(self):
        image=(ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
        with self.assertRaisesRegex(RuntimeError,'unexpectedly admitted'): run.reject_finalized(image)

    def worker_case(self,inject=False):
        store=run.cli.Store(ROOT)
        out=store.checked(Path(os.environ['P34_TEST_OUT'])/('mock-worker-postreset' if inject else 'mock-worker'))
        run.preflight(store,out)
        sdk=SDK(ORIGINAL+b'Z'*1992)
        store.write(out/'plan.json',dict(out=str(out),inputs=[run.cli.record(p) for p in run.SOURCES],
                    native_history_approved=str(run.base.HISTORY),connection_generation='c1'))
        class Observation:
            def __init__(self,dap,emit,seconds): self.dap=dap
            def connect(self): self.dap.ready=True
            def close(self): self.dap.close()
            def _check(self): pass
        def reader(*args,**kwargs): return Reader(*args,**kwargs,guard=lambda fn,*a,seconds:fn(*a))
        with mock.patch.object(run.base,'in_job',return_value=True), \
             mock.patch.object(run.base,'native_presence',return_value=dict(debugger_processes=[])), \
             mock.patch.object(run.base,'guarded',return_value=sdk), \
             mock.patch.object(run.base,'Dap',Dap), \
             mock.patch.object(Dap,'inject_post_reset',inject), \
             mock.patch.object(run.base,'Observation',Observation), \
             mock.patch.object(run,'Reader',side_effect=reader), \
             mock.patch.object(run.os,'add_dll_directory',return_value=contextlib.nullcontext()):
            self.assertEqual(run.worker(store,out),1 if inject else 0)
        result=store.read(out/'worker.json')
        self.assertTrue(result['close_returned'])
        self.assertEqual(result['result'],'FAILED' if inject else 'EXTENDED_OLD_APP_READ_FINALIZED_REJECTED')
        self.assertEqual(result['tail']['bytes'],1992)
        self.assertFalse(result['finalized_r2_admission'])
        if inject:self.assertTrue(result['reader']['reset_seen'])

    def test_complete_worker_mocked_native_and_owned_boundary(self):self.worker_case()

    def test_reset_during_post_idle_reads_blocks_success(self):self.worker_case(inject=True)


if __name__ == '__main__': unittest.main()
