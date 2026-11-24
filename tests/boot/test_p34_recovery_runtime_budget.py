from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
from p34_recovery_runtime_budget import Counter,extrapolate


class Tests(unittest.TestCase):
    def test_nonretaining_counters_keep_exact_operation_totals(self):
        count=Counter()
        for item in (('read',3,1),('read',0,1),('write',1,1,0),('erase',0x08010000),(0x08010000,0)):
            count.append(item)
        self.assertEqual(len(count),5)
        self.assertEqual(count.kinds,dict(read=2,write=1,erase=1,store=1))

    def test_extrapolation_is_linear_and_requires_finite_real_baseline(self):
        self.assertEqual(extrapolate(20,10,3),6)
        self.assertEqual(extrapolate(0,10,3),0)
        for args in ((-1,10,3),(True,10,3),(10,0,3),(10,True,3),(10,10,0),
                     (10,10,float('nan')),(10,10,float('inf')),(10,10,True)):
            with self.assertRaises(ValueError): extrapolate(*args)


if __name__=='__main__': unittest.main()
