from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'));sys.path.insert(0,str(ROOT/'tests/boot'))
from recovery_confirm import flash_remainder as impl
from recovery_confirm.native_io import Budget
import test_p34_recovery_ports as model


class Tests(unittest.TestCase):
    def test_late_complete_accepts_state_not_physical_deadline(self):
        for status,failed in ((0x20,False),(1,True),(0,True),(0x24,True)):
            clock=model.Clock();events=[]
            port=object.__new__(impl.ObservedSector)
            budget=Budget(30,clock)
            def read(address):clock.value+=.6;return status
            port.words=SimpleNamespace(budget=budget,read32=read,check=budget.left)
            port.status_reg=0x40023c0c;port.check=lambda:budget.left();port.sleep=clock.sleep
            port.emit=lambda e,**k:events.append((e,k))
            if failed:
                with self.assertRaises(ValueError):port.wait(.5)
                self.assertFalse(events)
            else:
                port.wait(.5)
                self.assertEqual(len(events),1)
                self.assertFalse(events[0][1]['physical_completion_within_phase_deadline_proven'])

    def test_global_budget_still_prevents_late_completion_acceptance(self):
        clock=model.Clock();port=object.__new__(impl.ObservedSector);budget=Budget(.1,clock)
        def read(address):clock.value+=.2;budget.left();return 0x20
        port.words=SimpleNamespace(budget=budget,read32=read,check=budget.left)
        port.status_reg=0;port.check=budget.left;port.sleep=clock.sleep
        port.emit=lambda *a,**k:self.fail('no late-success event after global expiry')
        with self.assertRaises(ValueError):port.wait(.5)

    def test_exact_no_erase_remainder_and_no_prefix_replay(self):
        partial=(ROOT/'.cache/p34-flash-failure-audit1/expected-envelope.bin').read_bytes()
        clock=model.Clock();sdk=model.FlashSDK(clock,partial)
        sdk.memory[impl.BANKS[0][2]]=1;sdk.memory[impl.BANKS[0][1]]=0x20
        port=impl.PartialSector(model.Dap(sdk),model.IMAGE,partial,lambda:True,lambda *a,**k:None,
                               clock=clock,sleep=clock.sleep,guard=lambda f,*a,**k:f(*a))
        result=port.run()
        self.assertEqual(result['erase_commands'],0)
        self.assertEqual(result['programmed_words'],512)
        self.assertEqual(sdk.write_log,list(port.plan))
        self.assertEqual(sdk.flash[:4096],partial[:4096])
        self.assertEqual(sdk.flash[4096:6144],model.IMAGE[4096:6144])
        self.assertEqual(sdk.flash[6144:],partial[6144:])
        before=list(sdk.write_log)
        with self.assertRaises(ValueError):port.run()
        self.assertEqual(sdk.write_log,before)


if __name__=='__main__':unittest.main()
