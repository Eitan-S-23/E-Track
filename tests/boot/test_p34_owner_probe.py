import struct
import contextlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"Tools/ota"))
sys.path.insert(0, str(ROOT/"tests/boot"))
from recovery_entry import owner_probe as op


class Reader:
    def __init__(self):
        self.memory, self.grants = {}, []
        self.ptrs = [0x20010000+i*0x4000 for i in range(9)]
        self.put(op.MANAGER+4, 0x20008000, 0x20008024, 0x20008040)
        self.put(0x20008000, *self.ptrs)
        for p in self.ptrs: self.put(p, 0x08080000, 0, op.MANAGER, 0x08050000)
        self.put(self.ptrs[-1], op.PAGE_VPTR, 0, op.MANAGER, op.PAGE_NAME)
    def put(self, address, *values):
        for i,v in enumerate(values): self.memory[address+i*4] = v
    def grant(self, address, size):
        op.ram_range(address,size); self.grants.append((address,address+size))
    def read(self, address, size):
        assert any(a <= address and address+size <= b for a,b in self.grants)
        return b"".join(self.memory.get(a,0).to_bytes(4,"little") for a in range(address,address+size,4))
    def name_bytes(self): return op.PAGE_TEXT


class OwnerTests(unittest.TestCase):
    def test_unique_idle_owner(self):
        r=Reader(); value=op.collect(r)
        self.assertTrue(value["no_scheduled_sd_ota_owner"])
        self.assertFalse(value["media_safe_reset_proven"])
        self.assertFalse(value["nor_settled_proven"])
        self.assertLessEqual(len(r.grants),32)

    def test_invalid_pool_or_pointer_rejected(self):
        for address,values in ((op.MANAGER+4,(0x40000000,0x40000024,0x40000040)),
                               (op.MANAGER+4,(0x20008000,0x20008028,0x20008040)),
                               (op.MANAGER+4,(0x20008000,0x20008024,0x20018000)),
                               (0x20008000,(0x20008004,0x20008004)),
                               (0x20008000,(0x40000000,))):
            r=Reader(); r.put(address,*values)
            with self.assertRaises((ValueError,AssertionError)): op.collect(r)

    def test_object_identity_and_bounded_name(self):
        for offset,value in ((0,0x08000000),(8,op.MANAGER+4),(12,op.PAGE_NAME+4)):
            r=Reader(); r.put(r.ptrs[-1]+offset,value)
            with self.assertRaises(ValueError): op.collect(r)
        r=Reader(); r.name_bytes=lambda:b"Wrong\0"
        with self.assertRaises(ValueError): op.collect(r)

    def test_pending_file_timer_phase_and_working_mode(self):
        for offset,value in ((0x44,1),(0x1470,0x20005000),(0x34e8,1),(0x34e8,0x100),
                             (0x34ec,2),(0x1284,1),(0x1284,2),(0x1284,3)):
            r=Reader(); r.put(r.ptrs[-1]+offset,value)
            self.assertFalse(op.collect(r)["no_scheduled_sd_ota_owner"])

    def test_error_preserved_not_mislabelled_success(self):
        r=Reader(); r.put(r.ptrs[-1]+0x1284,5); r.put(r.ptrs[-1]+0x13b4,0x00646162)
        value=op.collect(r)
        self.assertTrue(value["updater_error_observed"])
        self.assertTrue(value["no_scheduled_sd_ota_owner"])

    def test_unknown_state_is_not_idle(self):
        for offset,value in ((0x34ec,255),(0x44,2),(0x1284,6),(0x34e8,2)):
            r=Reader(); r.put(r.ptrs[-1]+offset,value)
            with self.assertRaises(ValueError): op.collect(r)

    def test_qspi_scope_has_no_consuming_fifo_or_keys(self):
        self.assertNotIn(0xa0001100,op.QSPI_REGS.values())
        self.assertFalse(any(0xa0001054 <= p <= 0xa00010fc for p in op.QSPI_REGS.values()))

    def test_bound_name_and_instruction_offsets(self):
        image=(ROOT/".cache/p34-native-image1/app-readback.bin").read_bytes()
        start=op.PAGE_NAME-0x08010000
        self.assertEqual(image[start:start+len(op.PAGE_TEXT)],op.PAGE_TEXT)
        for address,code in ((0x0803ccba,"d0e90157"),(0x08047d92,"95f8ec34"),
                             (0x08047d9c,"95f8e834"),(0x08047de6,"95f8e994"),
                             (0x08048b26,"95f84c32")):
            start=address-0x08010000
            self.assertEqual(image[start:start+len(bytes.fromhex(code))],bytes.fromhex(code))

    def test_worker_end_to_end_with_mocked_native_boundary(self):
        import p34_halted_probe as run
        import test_p34_control_probe as controls
        store=run.cli.Store(ROOT)
        out=store.checked(Path(os.environ["P34_TEST_OUT"])/"case-worker")
        run.preflight(store,out)
        fixture=Reader(); sdk=controls.SDK()
        sdk.memory.update(fixture.memory)
        previous=store.read(ROOT/".cache/p34-entry-wfi1/worker.json")
        context=previous["context"]
        sdk.memory.update({controls.DHCSR:0x30001,controls.PAUSE:0x1000,0xe000ef34:context["fpccr"]})
        sdk.core.update({15:context["pc"],16:context["xpsr"],17:context["msp"],20:context["control"]<<24})
        address=op.PAGE_NAME & ~3
        data=b"\0"*(op.PAGE_NAME-address)+op.PAGE_TEXT
        data=data.ljust(24,b"\0")
        for i in range(0,24,4): sdk.memory[address+i]=int.from_bytes(data[i:i+4],"little")
        class Observer(controls.Observer):
            def __init__(self,dap,emit,seconds): super().__init__(dap)
            def connect(self): self.dap.open(); self.dap.connect()
            def _check(self): pass
        store.write(out/"plan.json",dict(inputs=[run.cli.record(p) for p in run.SOURCES],out=str(out),
                                         native_history_approved=str(run.base.HISTORY)))
        with mock.patch.object(run.base,"in_job",return_value=True), \
             mock.patch.object(run.base,"native_presence",return_value=dict(usb=[],debugger_processes=[])), \
             mock.patch.object(run.base,"guarded",return_value=sdk), \
             mock.patch.object(run.base,"Observation",Observer), \
             mock.patch.object(run.os,"add_dll_directory",return_value=contextlib.nullcontext()):
            self.assertEqual(run.worker(store,out),0)
        result=store.read(out/"worker.json")
        self.assertEqual(result["result"],"HALTED_OWNER_CONFIG_OBSERVED")
        self.assertTrue(result["owner_samples"][0]["updater"]["no_scheduled_sd_ota_owner"])
        self.assertTrue(result["close_returned"])


if __name__=="__main__": unittest.main()
