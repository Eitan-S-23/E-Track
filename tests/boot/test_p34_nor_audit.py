import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
import p34_nor_audit as audit


class AuditTests(unittest.TestCase):
    def test_three_real_qualification_traces(self):
        for name, count in (('p34-host-nor-status1', 46), ('p34-host-nor-read1', 226), ('p34-host-nor-mapped1', 50)):
            area = ROOT/'.cache'/name
            worker = json.loads((area/'worker.json').read_text())
            value = audit.trace(area, worker)
            self.assertEqual(value['target_writes'], count)
            self.assertEqual(value['mutation_commands'], 0)

    def test_injected_high_level_or_out_of_scope_write_rejected(self):
        area = ROOT/'.cache/p34-host-nor-status1'
        worker = json.loads((area/'worker.json').read_text())
        text = (area/'sdk.log').read_text()
        original = Path.open
        mutations = ['CPU_WriteMem(4 bytes @ 0x20060000)\n'+text,
                     text+'\nJLINK_CORESIGHT_WriteAPDPReg(AP reg 0x01, 0xE000ED0C)\nreturns 0\n'
                          'JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x03, 0x05FA0004)\nreturns 0\n',
                     text.replace('Value=0x000000EF', 'Value=0x000000EE', 1)]
        for changed in mutations:
            self.assertNotEqual(changed, text)
            def opening(path, *args, **kwargs):
                return io.StringIO(changed) if path == area/'sdk.log' else original(path, *args, **kwargs)
            with mock.patch.object(Path, 'open', opening):
                with self.assertRaises(RuntimeError): audit.trace(area, worker)

    def test_quad_order_and_wrong_mutation_range_rejected(self):
        source = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
        target = audit.Targets(source)
        with self.assertRaises(RuntimeError): target.write(0xa0001004, 0, 0x23000052)
        target = audit.Targets(source)
        def command(words):
            for i, word in enumerate(words): target.write(0xa0001000+4*i, word, 0x23000052)
        command((0, 0x1000000, 0, 0x06000002))
        with self.assertRaises(RuntimeError): command((0x100000, 0x1000003, 0, 0x20000002))

    def test_fifo_auto_increment_and_wrong_payload_rejected(self):
        target = audit.Targets(); target.tx = (b'1234', 0)
        with self.assertRaises(RuntimeError): target.write(0xa0001100, int.from_bytes(b'1234', 'little'), 0x23000052)
        with self.assertRaises(RuntimeError): target.write(0xa0001100, 0, 0x23000042)
        target.write(0xa0001100, int.from_bytes(b'1234', 'little'), 0x23000042)
        self.assertIsNone(target.tx)


if __name__ == '__main__': unittest.main()
